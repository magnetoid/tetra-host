from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    key: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="usd", nullable=False)
    stripe_price_id: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    max_apps: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_domains: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cpu_millicores: Mapped[int] = mapped_column(Integer, default=500, nullable=False)
    mem_mb: Mapped[int] = mapped_column(Integer, default=512, nullable=False)
    disk_mb: Mapped[int] = mapped_column(Integer, default=2048, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
