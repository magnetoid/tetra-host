"""Scheduled-jobs service — tenant-scoped CRUD over ScheduledJob/JobRun. Session-based so both
the API handlers and the background scheduler share it. Ownership is fail-closed (a tenant only
sees/edits its own jobs → 404 otherwise)."""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import JobRun, ScheduledJob
from app.services.cron import is_valid_cron


class JobError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


ALLOWED_METHODS = {"GET", "POST", "HEAD"}


class JobsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_tenant(self, tenant_id: str | None) -> list[ScheduledJob]:
        rows = await self.session.scalars(
            select(ScheduledJob)
            .where(ScheduledJob.tenant_id == (tenant_id or ""))
            .order_by(ScheduledJob.created_at.desc())
        )
        return list(rows.all())

    async def _owned(self, tenant_id: str | None, job_id: str) -> ScheduledJob:
        job = await self.session.get(ScheduledJob, job_id)
        if job is None or job.tenant_id != (tenant_id or ""):
            raise JobError("Job not found.", status_code=404)
        return job

    async def create(
        self, tenant_id: str | None, *, name: str, cron: str, url: str, method: str = "GET"
    ) -> ScheduledJob:
        if not tenant_id:
            raise JobError("A tenant context is required.", status_code=400)
        if not name.strip():
            raise JobError("Name is required.", status_code=422)
        if not is_valid_cron(cron):
            raise JobError("Invalid cron expression (expected 5 fields).", status_code=422)
        if not (url.startswith("https://") or url.startswith("http://")):
            raise JobError("URL must be http(s).", status_code=422)
        method = method.upper()
        if method not in ALLOWED_METHODS:
            raise JobError(f"Method must be one of {sorted(ALLOWED_METHODS)}.", status_code=422)
        job = ScheduledJob(
            tenant_id=tenant_id, name=name.strip(), cron=cron.strip(), url=url.strip(), method=method
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def update(
        self, tenant_id: str | None, job_id: str, *,
        cron: str | None = None, url: str | None = None,
        method: str | None = None, enabled: bool | None = None,
    ) -> ScheduledJob:
        job = await self._owned(tenant_id, job_id)
        if cron is not None:
            if not is_valid_cron(cron):
                raise JobError("Invalid cron expression.", status_code=422)
            job.cron = cron.strip()
        if url is not None:
            if not (url.startswith("https://") or url.startswith("http://")):
                raise JobError("URL must be http(s).", status_code=422)
            job.url = url.strip()
        if method is not None:
            m = method.upper()
            if m not in ALLOWED_METHODS:
                raise JobError("Invalid method.", status_code=422)
            job.method = m
        if enabled is not None:
            job.enabled = enabled
        await self.session.flush()
        return job

    async def delete(self, tenant_id: str | None, job_id: str) -> None:
        job = await self._owned(tenant_id, job_id)
        await self.session.execute(delete(JobRun).where(JobRun.job_id == job.id))
        await self.session.delete(job)
        await self.session.flush()

    async def list_runs(self, tenant_id: str | None, job_id: str, *, limit: int = 20) -> list[JobRun]:
        await self._owned(tenant_id, job_id)
        rows = await self.session.scalars(
            select(JobRun).where(JobRun.job_id == job_id).order_by(JobRun.started_at.desc()).limit(limit)
        )
        return list(rows.all())
