"""Team / RBAC service.

Turns a single-owner tenant into a multi-user team: the owner mints
share-anywhere invite links (no email dependency on the box), invitees redeem
them to create their own login scoped to the tenant with a bounded role, and
the owner can change roles or deactivate members. All operations are strictly
tenant-scoped and fail closed.
"""

import hashlib
import secrets
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdminUser, TenantInvite
from app.models.admin import ROLE_OWNER, ROLE_PLATFORM_ADMIN
from app.modules.auth.service import AuthService
from app.models.team import (
    INVITABLE_ROLES,
    INVITE_ACCEPTED,
    INVITE_PENDING,
    INVITE_REVOKED,
)


class TeamError(Exception):
    """User-facing team-management error (maps to 4xx in the route layer)."""

    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class TeamService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.auth = AuthService(session)

    # ── Reads ────────────────────────────────────────────────────────────
    async def list_members(self, tenant_id: str) -> list[AdminUser]:
        result = await self.session.execute(
            select(AdminUser)
            .where(AdminUser.tenant_id == tenant_id)
            .order_by(AdminUser.created_at.asc())
        )
        return list(result.scalars().all())

    async def list_invites(self, tenant_id: str) -> list[TenantInvite]:
        result = await self.session.execute(
            select(TenantInvite)
            .where(
                TenantInvite.tenant_id == tenant_id,
                TenantInvite.status == INVITE_PENDING,
            )
            .order_by(TenantInvite.created_at.desc())
        )
        return list(result.scalars().all())

    async def _active_owner_count(self, tenant_id: str) -> int:
        result = await self.session.execute(
            select(AdminUser).where(
                AdminUser.tenant_id == tenant_id,
                AdminUser.role == ROLE_OWNER,
                AdminUser.is_active.is_(True),
            )
        )
        return len(list(result.scalars().all()))

    async def _member_in_tenant(self, tenant_id: str, member_id: str) -> AdminUser:
        result = await self.session.execute(
            select(AdminUser).where(
                AdminUser.id == member_id,
                AdminUser.tenant_id == tenant_id,
            )
        )
        member = result.scalar_one_or_none()
        if member is None:
            # 404, never leak whether the id exists in another tenant.
            raise TeamError("Member not found.", status_code=404)
        return member

    # ── Invites ──────────────────────────────────────────────────────────
    async def create_invite(
        self, tenant_id: str, inviter: AdminUser, email: str, role: str
    ) -> tuple[TenantInvite, str]:
        """Create a pending invite. Returns (invite, raw_token). The raw token
        is shown to the inviter exactly once; only its hash is stored."""
        role = (role or "").strip().lower()
        if role not in INVITABLE_ROLES:
            raise TeamError("Role must be 'admin' or 'member'.")

        normalized = self.auth.normalize_email(email)
        if not normalized or "@" not in normalized:
            raise TeamError("A valid email is required.")

        # Already an active member of THIS tenant → nothing to invite.
        existing = await self.auth.get_admin_by_email(normalized)
        if existing is not None and existing.tenant_id == tenant_id and existing.is_active:
            raise TeamError("That person is already on your team.")
        # Email belongs to an account in ANOTHER tenant — one login per email.
        if existing is not None and existing.tenant_id != tenant_id:
            raise TeamError("That email is already registered to another account.")

        # Dedupe: revoke any outstanding pending invite for the same email.
        prior = await self.session.execute(
            select(TenantInvite).where(
                TenantInvite.tenant_id == tenant_id,
                TenantInvite.email == normalized,
                TenantInvite.status == INVITE_PENDING,
            )
        )
        for stale in prior.scalars().all():
            stale.status = INVITE_REVOKED

        raw_token = secrets.token_urlsafe(32)
        invite = TenantInvite(
            tenant_id=tenant_id,
            email=normalized,
            role=role,
            token_hash=_hash_token(raw_token),
            status=INVITE_PENDING,
            invited_by_id=inviter.id,
        )
        self.session.add(invite)
        await self.session.flush()
        return invite, raw_token

    async def revoke_invite(self, tenant_id: str, invite_id: str) -> None:
        result = await self.session.execute(
            select(TenantInvite).where(
                TenantInvite.id == invite_id,
                TenantInvite.tenant_id == tenant_id,
            )
        )
        invite = result.scalar_one_or_none()
        if invite is None:
            raise TeamError("Invite not found.", status_code=404)
        if invite.status != INVITE_PENDING:
            raise TeamError("Invite is no longer pending.")
        invite.status = INVITE_REVOKED
        await self.session.flush()

    async def peek_invite(self, raw_token: str) -> TenantInvite | None:
        """Resolve a redeemable invite by raw token (for the accept page's
        pre-fill). Returns None if unknown/expired/used."""
        result = await self.session.execute(
            select(TenantInvite).where(TenantInvite.token_hash == _hash_token(raw_token))
        )
        invite = result.scalar_one_or_none()
        if invite is None or not invite.is_redeemable():
            return None
        return invite

    async def accept_invite(
        self, raw_token: str, full_name: str, password: str
    ) -> AdminUser:
        """Redeem an invite: create the teammate's account in the tenant with the
        invited role, and mark the invite accepted (single use)."""
        result = await self.session.execute(
            select(TenantInvite).where(TenantInvite.token_hash == _hash_token(raw_token))
        )
        invite = result.scalar_one_or_none()
        if invite is None or not invite.is_redeemable():
            raise TeamError("This invite link is invalid or has expired.", status_code=404)

        # Reject if a login already exists for the email (unique constraint).
        if await self.auth.get_admin_by_email(invite.email) is not None:
            raise TeamError("An account already exists for this email.", status_code=409)

        try:
            self.auth.validate_password(password)
        except ValueError as exc:
            raise TeamError(str(exc), status_code=422) from exc

        admin = AdminUser(
            tenant_id=invite.tenant_id,
            email=invite.email,
            full_name=full_name.strip() or invite.email,
            password_hash=self.auth.hash_password(password),
            is_active=True,
            role=invite.role,
        )
        self.session.add(admin)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            raise TeamError("An account already exists for this email.", status_code=409) from exc

        invite.status = INVITE_ACCEPTED
        invite.accepted_admin_id = admin.id
        invite.accepted_at = datetime.now(UTC)
        await self.session.flush()
        return await self.auth.get_admin_by_id(admin.id)

    # ── Members ──────────────────────────────────────────────────────────
    async def change_role(self, tenant_id: str, member_id: str, role: str) -> AdminUser:
        role = (role or "").strip().lower()
        if role not in INVITABLE_ROLES:
            raise TeamError("Role must be 'admin' or 'member'.")
        member = await self._member_in_tenant(tenant_id, member_id)
        if member.role == ROLE_PLATFORM_ADMIN:
            raise TeamError("Platform staff roles are managed separately.", status_code=403)
        if member.role == ROLE_OWNER and await self._active_owner_count(tenant_id) <= 1:
            raise TeamError("A tenant must keep at least one owner.")
        member.role = role
        await self.session.flush()
        return member

    async def remove_member(
        self, tenant_id: str, member_id: str, acting_admin: AdminUser
    ) -> AdminUser:
        member = await self._member_in_tenant(tenant_id, member_id)
        if member.id == acting_admin.id:
            raise TeamError("You cannot remove yourself.")
        if member.role == ROLE_PLATFORM_ADMIN:
            raise TeamError("Platform staff are managed separately.", status_code=403)
        if member.role == ROLE_OWNER and await self._active_owner_count(tenant_id) <= 1:
            raise TeamError("A tenant must keep at least one owner.")
        # Deactivate rather than delete — preserves audit trail + resource authorship.
        member.is_active = False
        await self.session.flush()
        return member
