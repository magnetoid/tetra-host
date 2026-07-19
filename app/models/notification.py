from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class NotificationChannel(Base):
    """An OUTBOUND webhook the platform POSTs to on tenant events (deploy
    succeeded/failed, …). Distinct from ``DeployHook``, which is INBOUND
    (GitHub → us). Works with any receiver that accepts a JSON POST — Slack,
    Discord, or a custom endpoint.

    ``secret`` is a shared HMAC key: every delivery is signed
    ``X-Tetra-Signature: sha256=<hmac(secret, body)>`` so the receiver can verify
    authenticity. We hold it in plaintext because we sign outgoing requests with
    it; it is the tenant's own secret for their own endpoint, not a Tetra credential.
    """

    __tablename__ = "notification_channels"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), index=True)
    name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    url: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    secret: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    # Comma-separated event types to deliver, or "*" for all.
    events: Mapped[str] = mapped_column(String(255), default="*", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Short result of the most recent delivery attempt, e.g. "ok", "http 500", "unreachable".
    last_status: Mapped[str] = mapped_column(String(60), default="", nullable=False)
