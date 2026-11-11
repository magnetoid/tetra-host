"""Import runs — moving an existing app (Coolify today, Plesk later) onto the Tetra Engine.

One row per migration attempt of one source app. ``summary`` is the non-secret plan and
progress (services, ports, volumes, probe results) shown to operators; ``secret_blob``
holds the encrypted source compose + .env, from which every step re-derives its stack.
"""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

IMPORT_PLANNED = "planned"
IMPORT_STAGING = "staging"
IMPORT_STAGED = "staged"
IMPORT_CUTTING_OVER = "cutting_over"
IMPORT_LIVE = "live"
IMPORT_ROLLING_BACK = "rolling_back"
IMPORT_ROLLED_BACK = "rolled_back"
IMPORT_FAILED = "failed"

IMPORT_BUSY_STATES = {IMPORT_STAGING, IMPORT_CUTTING_OVER, IMPORT_ROLLING_BACK}


def utc_now() -> datetime:
    return datetime.now(UTC)


class ImportRun(Base):
    __tablename__ = "import_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), index=True)
    source: Mapped[str] = mapped_column(String(20), default="coolify", nullable=False)
    source_ref: Mapped[str] = mapped_column(String(128), index=True)
    project: Mapped[str] = mapped_column(String(63), index=True)
    state: Mapped[str] = mapped_column(String(20), default=IMPORT_PLANNED, nullable=False)
    summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    secret_blob: Mapped[str] = mapped_column(Text, default="", nullable=False)
    log: Mapped[str] = mapped_column(Text, default="", nullable=False)
    error: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    created_by: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
