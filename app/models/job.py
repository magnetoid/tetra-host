"""Scheduled jobs — cron-triggered HTTP calls run by the in-process scheduler.

A tenant defines a job (cron + URL); the scheduler fires it at each matching minute, recording
a JobRun. Safe by construction: it only makes an outbound HTTP request (no shell, no container
exec). Powers user "ping my /cron endpoint" needs plus internal maintenance jobs later.
"""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

JOB_STATUS_OK = "ok"
JOB_STATUS_ERROR = "error"


def utc_now() -> datetime:
    return datetime.now(UTC)


class ScheduledJob(Base):
    __tablename__ = "scheduled_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), index=True)
    name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    cron: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    url: Mapped[str] = mapped_column(String(2048), default="", nullable=False)
    method: Mapped[str] = mapped_column(String(10), default="GET", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    last_status: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    last_detail: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class JobRun(Base):
    __tablename__ = "job_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    job_id: Mapped[str] = mapped_column(String(36), index=True)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True)
    status: Mapped[str] = mapped_column(String(20), default=JOB_STATUS_OK, nullable=False)
    detail: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True, nullable=False)
