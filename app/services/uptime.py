"""Uptime monitoring — periodic HTTP probes of tenant-owned URLs.

The scheduler calls :meth:`UptimeService.run_all_due` once a minute. Each enabled
monitor is probed; the latest status/latency is recorded; and on a state
*transition* (up→down or down→up) an ``app.down`` / ``app.up`` event is dispatched
through the tenant's notification channels. Probes are best-effort — a slow or
dead target is recorded as ``down``, never raised.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import UptimeMonitor
from app.models.uptime import UPTIME_DOWN, UPTIME_UNKNOWN, UPTIME_UP
from app.services.notifications import NotificationService

logger = logging.getLogger(__name__)

APP_DOWN = "app.down"
APP_UP = "app.up"

Notifier = Callable[[str, str, dict[str, Any]], Awaitable[Any]]


class UptimeService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.session = session
        self._transport = transport
        self._timeout = timeout

    async def list_for_tenant(self, tenant_id: str) -> list[UptimeMonitor]:
        rows = await self.session.execute(
            select(UptimeMonitor)
            .where(UptimeMonitor.tenant_id == tenant_id)
            .order_by(UptimeMonitor.created_at.desc())
        )
        return list(rows.scalars())

    async def get(self, tenant_id: str, monitor_id: str) -> UptimeMonitor | None:
        monitor = await self.session.get(UptimeMonitor, monitor_id)
        if monitor is None or monitor.tenant_id != tenant_id:
            return None
        return monitor

    async def create(self, tenant_id: str, *, name: str, url: str) -> UptimeMonitor:
        monitor = UptimeMonitor(tenant_id=tenant_id, name=name.strip(), url=url.strip())
        self.session.add(monitor)
        await self.session.flush()
        return monitor

    async def delete(self, tenant_id: str, monitor_id: str) -> bool:
        monitor = await self.get(tenant_id, monitor_id)
        if monitor is None:
            return False
        await self.session.delete(monitor)
        await self.session.flush()
        return True

    async def probe(self, url: str) -> tuple[str, int, str]:
        """Return (status, latency_ms, detail) for one probe. 2xx/3xx = up."""
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(
                transport=self._transport, timeout=self._timeout, follow_redirects=False
            ) as client:
                resp = await client.get(url)
            latency = int((time.monotonic() - start) * 1000)
            if resp.status_code < 400:
                return UPTIME_UP, latency, f"HTTP {resp.status_code}"
            return UPTIME_DOWN, latency, f"HTTP {resp.status_code}"
        except (httpx.HTTPError, OSError) as exc:
            latency = int((time.monotonic() - start) * 1000)
            return UPTIME_DOWN, latency, str(exc)[:255] or "unreachable"

    @staticmethod
    def _should_alert(previous: str, current: str) -> bool:
        # Alert on any real transition, but not the first-ever up (unknown→up is
        # "came online", nothing was wrong). unknown→down still alerts.
        if current == previous:
            return False
        return not (previous == UPTIME_UNKNOWN and current == UPTIME_UP)

    async def check_one(self, monitor: UptimeMonitor, notify: Notifier | None = None) -> str:
        """Probe one monitor, persist the result, and alert on a transition."""
        previous = monitor.status
        current, latency, detail = await self.probe(monitor.url)
        monitor.status = current
        monitor.last_checked_at = datetime.now(UTC)
        monitor.last_latency_ms = latency
        monitor.last_detail = detail
        await self.session.flush()

        if self._should_alert(previous, current):
            event = APP_DOWN if current == UPTIME_DOWN else APP_UP
            payload = {
                "monitor": monitor.name,
                "url": monitor.url,
                "status": current,
                "latency_ms": latency,
                "detail": detail,
            }
            dispatch = notify or self._default_notify
            try:
                await dispatch(monitor.tenant_id, event, payload)
            except Exception:  # noqa: BLE001 — alerting must never break the check loop
                logger.warning("uptime alert dispatch failed for monitor %s", monitor.id, exc_info=True)
        return current

    async def _default_notify(self, tenant_id: str, event: str, payload: dict[str, Any]) -> None:
        await NotificationService(self.session).dispatch(tenant_id, event, payload)

    async def run_all_due(self, notify: Notifier | None = None) -> int:
        """Probe every enabled monitor across all tenants. Returns how many ran."""
        rows = await self.session.execute(
            select(UptimeMonitor).where(UptimeMonitor.enabled.is_(True))
        )
        monitors = list(rows.scalars())
        for monitor in monitors:
            await self.check_one(monitor, notify)
        return len(monitors)
