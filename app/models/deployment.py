from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Deployment status — the small, legible state model (Vercel-style).
STATUS_QUEUED = "queued"
STATUS_BUILDING = "building"
STATUS_READY = "ready"
STATUS_ERROR = "error"


def utc_now() -> datetime:
    return datetime.now(UTC)


class Deployment(Base):
    """A git build+run for a tenant. Built asynchronously; the row carries live status + log tail."""

    __tablename__ = "deployments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), index=True)
    project: Mapped[str] = mapped_column(String(120), index=True)
    git_url: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    ref: Mapped[str] = mapped_column(String(120), default="main", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=STATUS_QUEUED, nullable=False)
    builder: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    image: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    commit: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    domain: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    port: Mapped[int] = mapped_column(default=0, nullable=False)
    log: Mapped[str] = mapped_column(Text, default="", nullable=False)
    error: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
