"""Personal API token lifecycle — create / list / revoke / authenticate.

Tokens are ``tetra_<random>`` bearer secrets. Only a SHA-256 hash is persisted
(``ApiToken.token_hash``); the plaintext is returned to the caller exactly once
at creation and never stored. Authentication is a single indexed lookup by hash
that also enforces revocation + expiry and records ``last_used_at``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdminUser, ApiToken
from app.models.api_token import utc_now

TOKEN_PREFIX = "tetra_"
# Bytes of entropy in the random part (token_urlsafe → ~1.3 chars/byte).
_TOKEN_ENTROPY_BYTES = 32
# Length of the non-secret display prefix stored/shown (e.g. "tetra_a1b2c3d4").
_DISPLAY_PREFIX_LEN = len(TOKEN_PREFIX) + 8


def looks_like_personal_token(token: str) -> bool:
    return token.startswith(TOKEN_PREFIX)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass
class CreatedToken:
    """The one-time reveal returned from :meth:`ApiTokenService.create`."""

    row: ApiToken
    secret: str  # full plaintext — shown once, never persisted


class ApiTokenService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        admin: AdminUser,
        name: str,
        expires_in_days: int | None = None,
    ) -> CreatedToken:
        """Mint a new token for ``admin``. Returns the row + the one-time secret."""
        secret = f"{TOKEN_PREFIX}{token_urlsafe(_TOKEN_ENTROPY_BYTES)}"
        expires_at: datetime | None = None
        if expires_in_days and expires_in_days > 0:
            expires_at = utc_now() + timedelta(days=expires_in_days)
        row = ApiToken(
            tenant_id=admin.tenant_id,
            admin_user_id=admin.id,
            name=(name or "").strip()[:120] or "token",
            prefix=secret[:_DISPLAY_PREFIX_LEN],
            token_hash=hash_token(secret),
            expires_at=expires_at,
        )
        self._session.add(row)
        await self._session.flush()
        return CreatedToken(row=row, secret=secret)

    async def list_for_admin(self, admin: AdminUser) -> list[ApiToken]:
        """All non-revoked tokens for this admin, newest first."""
        result = await self._session.scalars(
            select(ApiToken)
            .where(
                ApiToken.admin_user_id == admin.id,
                ApiToken.revoked == False,  # noqa: E712 — SQL boolean, not Python identity
            )
            .order_by(ApiToken.created_at.desc())
        )
        return list(result.all())

    async def revoke(self, admin: AdminUser, token_id: str) -> bool:
        """Revoke one of the admin's own tokens. Returns False if not found/owned."""
        row = await self._session.get(ApiToken, token_id)
        if row is None or row.admin_user_id != admin.id or row.revoked:
            return False
        row.revoked = True
        await self._session.flush()
        return True

    async def authenticate(self, token: str) -> str | None:
        """Resolve a bearer token to its admin_user_id, or None if invalid.

        Enforces revocation + expiry and records ``last_used_at`` (best-effort).
        """
        row = await self._session.scalar(
            select(ApiToken).where(ApiToken.token_hash == hash_token(token))
        )
        if row is None or row.revoked:
            return None
        if row.expires_at is not None:
            expires_at = row.expires_at
            # Stored naive (SQLite) → assume UTC so the comparison is tz-aware.
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if expires_at < utc_now():
                return None
        row.last_used_at = utc_now()
        await self._session.flush()
        return row.admin_user_id
