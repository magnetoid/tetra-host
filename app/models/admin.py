from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

ROLE_PLATFORM_ADMIN = "platform_admin"
ROLE_OWNER = "owner"


def utc_now() -> datetime:
    return datetime.now(UTC)


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    role: Mapped[str] = mapped_column(String(20), default=ROLE_OWNER, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # --- Optional TOTP two-factor auth (opt-in; disabled leaves login unchanged) ---
    # `totp_secret` holds a pending secret after setup and the active secret once
    # enabled; enforcement keys off `totp_enabled` only. `totp_backup_codes` is a
    # JSON array of sha256-hashed one-time recovery codes.
    totp_secret: Mapped[str | None] = mapped_column(String(64))
    # server_default so raw-SQL / legacy-migration inserts (which don't apply the
    # ORM-side default) still satisfy NOT NULL — matches migration 0003.
    totp_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )
    totp_backup_codes: Mapped[str | None] = mapped_column(Text)

    tenant = relationship("Tenant", back_populates="admins")
