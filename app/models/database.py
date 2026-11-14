"""Managed databases — a tenant's Postgres/MySQL/MariaDB/Redis running on the Tetra Engine.

Each database is its own compose stack (``project``) with a named data volume, reachable only
from the tenant's private Docker network under its ``name``. Credentials are one Fernet
ciphertext (``app.services.secrets``) holding a JSON object; the plaintext is never stored.
"""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

BACKUP_RUNNING = "running"
BACKUP_OK = "ok"
BACKUP_ERROR = "error"

TRIGGER_MANUAL = "manual"
TRIGGER_SCHEDULED = "scheduled"


def utc_now() -> datetime:
    return datetime.now(UTC)


class ManagedDatabase(Base):
    __tablename__ = "managed_databases"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_managed_db_tenant_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), index=True)
    name: Mapped[str] = mapped_column(String(63), nullable=False)
    engine: Mapped[str] = mapped_column(String(20), nullable=False)
    version: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    project: Mapped[str] = mapped_column(String(63), unique=True, nullable=False)
    # The environment it was created into; ``None`` lets the workspace sync place it.
    environment_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    secret: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # Cron (UTC) for scheduled backups; empty turns them off.
    backup_cron: Mapped[str] = mapped_column(String(120), default="0 3 * * *", nullable=False)
    # How many scheduled backups to keep; manual backups are kept until deleted.
    backup_keep: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class DatabaseBackup(Base):
    __tablename__ = "database_backups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    database_id: Mapped[str] = mapped_column(String(36), index=True)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True)
    status: Mapped[str] = mapped_column(String(20), default=BACKUP_RUNNING, nullable=False)
    trigger: Mapped[str] = mapped_column(String(20), default=TRIGGER_MANUAL, nullable=False)
    # Path relative to DATABASE_BACKUP_DIR; never shown to tenants.
    filename: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    error: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    # Last restore from this backup: "" (never), running, ok or error.
    restore_status: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    restore_error: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    restored_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
