from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class DeployHook(Base):
    """A GitHub push-to-deploy webhook for a native (Tetra Engine) app.

    A push to ``ref`` triggers a redeploy of ``project`` from ``git_url``. ``secret``
    holds a Fernet ciphertext of the HMAC secret shared with GitHub (see
    app.services.secrets); the plaintext is shown to the owner only once at creation.
    """

    __tablename__ = "deploy_hooks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), index=True)
    project: Mapped[str] = mapped_column(String(120), index=True)
    git_url: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    ref: Mapped[str] = mapped_column(String(120), default="main", nullable=False)
    port: Mapped[int] = mapped_column(Integer, default=3000, nullable=False)
    secret: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Vercel-parity default: pushes to non-production branches get preview environments.
    previews: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
