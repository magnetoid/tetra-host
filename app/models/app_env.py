from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class AppEnvVar(Base):
    """A tenant-scoped environment variable for a native (Tetra Engine) app.

    ``value`` holds a Fernet ciphertext (see app.services.secrets); the plaintext is
    never persisted. Unique per (tenant, project, key). ``is_build_time`` is recorded
    for future build-arg support; today all vars are injected at runtime.
    """

    __tablename__ = "app_env_vars"
    __table_args__ = (
        UniqueConstraint("tenant_id", "project", "key", name="uq_app_env_scope_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), index=True)
    project: Mapped[str] = mapped_column(String(120), index=True)
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_build_time: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
