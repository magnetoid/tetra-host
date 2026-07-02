from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class PreviewEnv(Base):
    """An ephemeral per-branch preview of a native app (Vercel-style preview environment).

    A push to a non-production branch of a hooked repo deploys ``preview_project``
    (its own Tetra Engine stack + subdomain); deleting the branch tears it down.
    Previews don't hold a quota slot — they are capped per project instead
    (``max_previews_per_project``) and run with default resource limits.
    """

    __tablename__ = "preview_envs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "project", "branch", name="uq_preview_tenant_project_branch"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), index=True)
    project: Mapped[str] = mapped_column(String(120), index=True)
    branch: Mapped[str] = mapped_column(String(200), nullable=False)
    preview_project: Mapped[str] = mapped_column(String(160), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    last_deployment_id: Mapped[str] = mapped_column(String(36), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
