"""Personal API tokens — named, long-lived, individually revocable bearer tokens.

Unlike the stateless signed token minted at login (``app/api/security.py``), a
personal API token is a first-class DB row a user creates for CLI/CI/automation:
it can be named, listed, and revoked independently, and it survives past a login
session. Only a SHA-256 hash of the secret is stored; the plaintext is shown to
the caller exactly once at creation. A short non-secret ``prefix`` is kept for
display so a user can tell their tokens apart in the list.
"""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class ApiToken(Base):
    __tablename__ = "api_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), index=True)
    admin_user_id: Mapped[str] = mapped_column(String(36), index=True)
    name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    # Non-secret display prefix, e.g. "tetra_a1b2c3d4"; lets a user identify a token.
    prefix: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    # SHA-256 hex of the full secret. Unique so authentication is a single indexed lookup.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Optional expiry; NULL = never expires.
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
