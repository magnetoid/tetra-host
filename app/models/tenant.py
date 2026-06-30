from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

TENANT_PENDING = "pending"
TENANT_ACTIVE = "active"
TENANT_SUSPENDED = "suspended"
TENANT_REJECTED = "rejected"


def utc_now() -> datetime:
    return datetime.now(UTC)


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default=TENANT_ACTIVE, nullable=False)
    plan_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("plans.id"), nullable=True)
    is_platform_scope: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    admins = relationship("AdminUser", back_populates="tenant")

    @property
    def is_active(self) -> bool:
        return self.status == TENANT_ACTIVE
