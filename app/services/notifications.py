"""Outbound webhook notifications — deliver signed event payloads to tenant-owned
endpoints (Slack / Discord / custom) on platform events like deploy outcomes.

Delivery is best-effort and self-contained: a failing or slow webhook must NEVER
affect the action that triggered it (e.g. a deploy), so every network path is
caught and recorded as ``last_status`` rather than raised. Each request is signed
``X-Tetra-Signature: sha256=<hmac(secret, body)>`` so receivers can verify it.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import NotificationChannel

logger = logging.getLogger(__name__)

DEPLOY_SUCCEEDED = "deploy.succeeded"
DEPLOY_FAILED = "deploy.failed"
TEST_EVENT = "test"
KNOWN_EVENTS = (DEPLOY_SUCCEEDED, DEPLOY_FAILED)


def _normalize_events(events: str | None) -> str:
    """Return a clean subscription string: ``*`` (all) or a comma-separated list."""
    value = (events or "*").strip()
    if not value or value == "*":
        return "*"
    parts = [p.strip() for p in value.split(",") if p.strip()]
    return ",".join(parts) or "*"


class NotificationService:
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

    @staticmethod
    def generate_secret() -> str:
        return "whsec_" + secrets.token_hex(24)

    @staticmethod
    def sign(secret: str, body: bytes) -> str:
        return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

    async def create(
        self, tenant_id: str, *, name: str, url: str, events: str | None = "*"
    ) -> NotificationChannel:
        channel = NotificationChannel(
            tenant_id=tenant_id,
            name=name.strip(),
            url=url.strip(),
            secret=self.generate_secret(),
            events=_normalize_events(events),
        )
        self.session.add(channel)
        await self.session.flush()
        return channel

    async def list_for_tenant(self, tenant_id: str) -> list[NotificationChannel]:
        rows = await self.session.execute(
            select(NotificationChannel)
            .where(NotificationChannel.tenant_id == tenant_id)
            .order_by(NotificationChannel.created_at.desc())
        )
        return list(rows.scalars())

    async def get(self, tenant_id: str, channel_id: str) -> NotificationChannel | None:
        channel = await self.session.get(NotificationChannel, channel_id)
        if channel is None or channel.tenant_id != tenant_id:
            return None
        return channel

    async def delete(self, tenant_id: str, channel_id: str) -> bool:
        channel = await self.get(tenant_id, channel_id)
        if channel is None:
            return False
        await self.session.delete(channel)
        await self.session.flush()
        return True

    def _subscribed(self, channel: NotificationChannel, event_type: str) -> bool:
        if not channel.enabled:
            return False
        if channel.events.strip() == "*":
            return True
        wanted = {e.strip() for e in channel.events.split(",") if e.strip()}
        return event_type in wanted

    async def deliver(
        self, channel: NotificationChannel, event_type: str, payload: dict[str, Any]
    ) -> tuple[bool, str]:
        """POST one signed event to one channel; record + return (ok, status_label)."""
        body = json.dumps(
            {"event": event_type, "data": payload}, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "X-Tetra-Event": event_type,
            "X-Tetra-Signature": self.sign(channel.secret, body),
            "User-Agent": "Tetra-Host-Notifications/1",
        }
        ok = False
        status_label = "unreachable"
        try:
            async with httpx.AsyncClient(transport=self._transport, timeout=self._timeout) as client:
                resp = await client.post(channel.url, content=body, headers=headers)
            ok = 200 <= resp.status_code < 300
            status_label = "ok" if ok else f"http {resp.status_code}"
        except (httpx.HTTPError, OSError) as exc:
            logger.warning("notification delivery to channel %s failed: %s", channel.id, exc)
        channel.last_delivered_at = datetime.now(UTC)
        channel.last_status = status_label
        await self.session.flush()
        return ok, status_label

    async def dispatch(self, tenant_id: str, event_type: str, payload: dict[str, Any]) -> int:
        """Deliver ``event_type`` to every subscribed channel. Returns attempts made.

        Best-effort: individual delivery failures are recorded, never raised.
        """
        channels = [
            c for c in await self.list_for_tenant(tenant_id) if self._subscribed(c, event_type)
        ]
        for channel in channels:
            await self.deliver(channel, event_type, payload)
        return len(channels)
