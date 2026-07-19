from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

UPTIME_UNKNOWN = "unknown"
UPTIME_UP = "up"
UPTIME_DOWN = "down"


def utc_now() -> datetime:
    return datetime.now(UTC)


class UptimeMonitor(Base):
    """A tenant-owned HTTP uptime check. The in-process scheduler probes ``url``
    on a fixed cadence, records the latest ``status``/latency, and (via the
    notification channels) fires ``app.down`` / ``app.up`` on a state transition.
    """

    __tablename__ = "uptime_monitors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), index=True)
    name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    url: Mapped[str] = mapped_column(String(2048), default="", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(10), default=UPTIME_UNKNOWN, nullable=False)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_detail: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
