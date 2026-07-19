"""In-process cron scheduler — fires due ScheduledJobs at each minute boundary.

A single asyncio task started in the app lifespan. Every minute it loads enabled jobs, matches
them against the wall clock (UTC) with the dependency-free ``cron_matches``, makes the outbound
HTTP call, and records a JobRun. Errors never kill the loop. Suited to a single-instance panel;
a multi-instance deploy would move this to a leader/queue (documented follow-up).
"""

import asyncio
import logging
import time
from datetime import UTC, datetime

import httpx
from sqlalchemy import select

from app.db import session_scope
from app.models.job import JOB_STATUS_ERROR, JOB_STATUS_OK, JobRun, ScheduledJob
from app.services.cron import cron_matches

logger = logging.getLogger("tetra.scheduler")


async def _execute(http_client: httpx.AsyncClient, job: ScheduledJob) -> tuple[str, str, int]:
    start = time.monotonic()
    try:
        resp = await http_client.request(job.method, job.url, timeout=30.0)
        duration = int((time.monotonic() - start) * 1000)
        if resp.status_code < 400:
            return JOB_STATUS_OK, str(resp.status_code), duration
        return JOB_STATUS_ERROR, f"HTTP {resp.status_code}"[:500], duration
    except httpx.HTTPError as exc:
        return JOB_STATUS_ERROR, str(exc)[:500], int((time.monotonic() - start) * 1000)


async def run_due_jobs(http_client: httpx.AsyncClient, now: datetime) -> int:
    """Run every enabled job whose cron matches ``now``. Returns how many fired."""
    async with session_scope() as session:
        jobs = list(
            (await session.scalars(select(ScheduledJob).where(ScheduledJob.enabled.is_(True)))).all()
        )
        due = [job for job in jobs if cron_matches(job.cron, now)]
        for job in due:
            status, detail, duration = await _execute(http_client, job)
            if status == JOB_STATUS_ERROR:
                logger.warning("scheduled job %s (%s) failed: %s", job.id, job.name, detail)
            session.add(
                JobRun(
                    job_id=job.id, tenant_id=job.tenant_id, status=status,
                    detail=detail, duration_ms=duration,
                )
            )
            job.last_run_at = now
            job.last_status = status
            job.last_detail = detail
        return len(due)


async def run_uptime_checks() -> int:
    """Probe every enabled uptime monitor and alert on transitions. Self-contained
    (own session + own per-probe clients); imported lazily so the scheduler module
    stays dependency-light."""
    from app.services.uptime import UptimeService

    async with session_scope() as session:
        return await UptimeService(session).run_all_due()


async def scheduler_loop(app) -> None:
    uptime_enabled = getattr(app.state, "uptime_checks_enabled", True)
    while True:
        now = datetime.now(UTC)
        await asyncio.sleep(max(1.0, 60 - now.second - now.microsecond / 1_000_000))
        tick = datetime.now(UTC).replace(second=0, microsecond=0)
        try:
            fired = await run_due_jobs(app.state.http_client, tick)
            if fired:
                logger.info("scheduler fired %d job(s) at %s", fired, tick.isoformat())
        except Exception:  # noqa: BLE001 — a scheduler error must never kill the loop
            logger.exception("scheduler tick failed")
        if uptime_enabled:
            try:
                checked = await run_uptime_checks()
                if checked:
                    logger.debug("uptime probed %d monitor(s) at %s", checked, tick.isoformat())
            except Exception:  # noqa: BLE001 — uptime probing must never kill the loop
                logger.exception("uptime check tick failed")


def start_scheduler(app) -> None:
    app.state._scheduler_task = asyncio.create_task(scheduler_loop(app))


async def stop_scheduler(app) -> None:
    task = getattr(app.state, "_scheduler_task", None)
    if task is not None:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
