from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Assignable tenant roles for invited teammates. `owner` and `platform_admin`
# are deliberately NOT invitable — ownership transfer and platform staff are
# separate, higher-privilege flows. See app/models/admin.py for the full set.
ROLE_ADMIN = "admin"
ROLE_MEMBER = "member"
INVITABLE_ROLES = frozenset({ROLE_ADMIN, ROLE_MEMBER})

INVITE_PENDING = "pending"
INVITE_ACCEPTED = "accepted"
INVITE_REVOKED = "revoked"

# How long a fresh invite link stays valid.
INVITE_TTL_DAYS = 14


def utc_now() -> datetime:
    return datetime.now(UTC)


def default_expiry() -> datetime:
    return utc_now() + timedelta(days=INVITE_TTL_DAYS)


class TenantInvite(Base):
    """A pending invitation for someone to join a tenant with a given role.

    Delivered as a share-anywhere link (no email dependency on the box): the
    owner is shown the raw token exactly once at creation; only its SHA-256
    hash is persisted, so a leaked database row cannot be redeemed.
    """

    __tablename__ = "tenant_invites"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    role: Mapped[str] = mapped_column(String(20), default=ROLE_MEMBER, nullable=False)
    # SHA-256 hex of the raw invite token — never the token itself.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default=INVITE_PENDING, nullable=False)
    invited_by_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    accepted_admin_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=default_expiry, nullable=False
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def is_redeemable(self, *, now: datetime | None = None) -> bool:
        moment = now or utc_now()
        expires = self.expires_at
        if expires is not None and expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        return self.status == INVITE_PENDING and (expires is None or expires > moment)
