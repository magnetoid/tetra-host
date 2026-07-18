"""OIDC Identity Provider — Tetra as the IdP so Mailcow can drop an already
authenticated tenant straight into SOGo webmail (Mailcow "Proxy Auth").

Design (see docs/providers/combined-api-reference.md → Mailcow OIDC):
  1. The console's "Open webmail" button hits /oidc/launch?mailbox=… — a
     session-authenticated Tetra route that verifies the tenant OWNS the mailbox
     (fail-closed) and stashes the selection in the session, then bounces the
     browser to Mailcow's OIDC login.
  2. Mailcow redirects the browser to /oidc/authorize. We require a live Tetra
     session, re-verify ownership of the stashed mailbox, mint a single-use code
     bound to that mailbox, and redirect back to Mailcow's redirect_uri.
  3. Mailcow calls /oidc/token (client-secret auth) → we return a signed RS256
     id_token asserting email=<mailbox>. Mailcow matches the mailbox by email and
     proxy-auths the browser into SOGo.

Only ONE client is registered (Mailcow), from config. Codes + access tokens live
in the shared TTLCache, single-use, short-lived. Dormant unless `oidc_configured`.
"""

from __future__ import annotations

import secrets
from typing import Any

from fastapi import Request

from app.config import get_settings
from app.services.oidc_keys import OIDCSigningKey, load_signing_key, now_ts

# Lifetimes (seconds).
CODE_TTL = 300
TOKEN_TTL = 600
ID_TOKEN_TTL = 600
# mailcow auto-provisioning template claim (Mailcow "mailcow_template" scope).
DEFAULT_MAILCOW_TEMPLATE = "Default"


class OIDCError(Exception):
    """OAuth/OIDC protocol error. `error` is the RFC 6749 code; `status_code`
    the HTTP status for the token/userinfo endpoints."""

    def __init__(self, error: str, description: str = "", *, status_code: int = 400) -> None:
        super().__init__(description or error)
        self.error = error
        self.description = description
        self.status_code = status_code


class OIDCService:
    SESSION_MAILBOX_KEY = "oidc_mailbox"

    def __init__(self, request: Request) -> None:
        self.request = request
        self.settings = get_settings()
        self.cache = request.app.state.cache

    def is_configured(self) -> bool:
        return self.settings.oidc_configured

    def _require_configured(self) -> None:
        if not self.is_configured():
            raise OIDCError(
                "temporarily_unavailable", "OIDC is not configured.", status_code=503
            )

    def signing_key(self) -> OIDCSigningKey:
        return load_signing_key(self.settings.oidc_private_key_pem)

    @property
    def issuer(self) -> str:
        return self.settings.oidc_issuer.rstrip("/")

    # ── Discovery + JWKS ─────────────────────────────────────────────────────

    def discovery_document(self) -> dict[str, Any]:
        base = self.issuer
        return {
            "issuer": base,
            "authorization_endpoint": f"{base}/oidc/authorize",
            "token_endpoint": f"{base}/oidc/token",
            "userinfo_endpoint": f"{base}/oidc/userinfo",
            "jwks_uri": f"{base}/oidc/jwks",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code"],
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": ["RS256"],
            "scopes_supported": ["openid", "profile", "email", "mailcow_template"],
            "token_endpoint_auth_methods_supported": [
                "client_secret_post",
                "client_secret_basic",
            ],
            "claims_supported": [
                "sub", "email", "email_verified", "preferred_username",
                "name", "mailcow_template", "aud", "iss", "iat", "exp", "nonce",
            ],
        }

    def jwks(self) -> dict[str, Any]:
        return self.signing_key().jwks()

    # ── Client + redirect validation ─────────────────────────────────────────

    def validate_client_id(self, client_id: str) -> None:
        if client_id != self.settings.oidc_client_id:
            raise OIDCError("unauthorized_client", "Unknown client_id.")

    def validate_redirect_uri(self, redirect_uri: str) -> None:
        # Exact-match allowlist — never prefix/substring match (open-redirect risk).
        if redirect_uri not in self.settings.oidc_redirect_uris:
            raise OIDCError("invalid_request", "redirect_uri is not registered.")

    def validate_client_credentials(self, client_id: str, client_secret: str) -> None:
        expected_id = self.settings.oidc_client_id
        expected_secret = self.settings.oidc_client_secret
        # Constant-time compare on the secret; both must match.
        ok_id = secrets.compare_digest(client_id or "", expected_id)
        ok_secret = secrets.compare_digest(client_secret or "", expected_secret)
        if not (ok_id and ok_secret):
            raise OIDCError("invalid_client", "Client authentication failed.", status_code=401)

    # ── Selected mailbox (set by /oidc/launch, read by /oidc/authorize) ──────

    def set_selected_mailbox(self, username: str, name: str) -> None:
        self.request.session[self.SESSION_MAILBOX_KEY] = {"username": username, "name": name}

    def take_selected_mailbox(self) -> dict[str, str] | None:
        """Read AND clear the selection — a code is minted once per launch."""
        return self.request.session.pop(self.SESSION_MAILBOX_KEY, None)

    # ── Authorization code ───────────────────────────────────────────────────

    async def issue_code(
        self,
        *,
        mailbox: str,
        name: str,
        client_id: str,
        redirect_uri: str,
        scope: str,
        nonce: str | None,
    ) -> str:
        self._require_configured()
        code = secrets.token_urlsafe(32)
        await self.cache.set(
            f"oidc:code:{code}",
            {
                "mailbox": mailbox,
                "name": name,
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "scope": scope,
                "nonce": nonce,
            },
            CODE_TTL,
        )
        return code

    async def exchange_code(
        self,
        *,
        code: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
    ) -> dict[str, Any]:
        self._require_configured()
        self.validate_client_credentials(client_id, client_secret)

        entry = await self.cache.get(f"oidc:code:{code}")
        if not isinstance(entry, dict):
            raise OIDCError("invalid_grant", "Authorization code is invalid or expired.")
        # Single-use: burn it immediately so a replay can't mint a second token.
        await self.cache.delete(f"oidc:code:{code}")

        if entry["client_id"] != client_id:
            raise OIDCError("invalid_grant", "Code was issued to a different client.")
        if entry["redirect_uri"] != redirect_uri:
            raise OIDCError("invalid_grant", "redirect_uri mismatch.")

        mailbox = entry["mailbox"]
        name = entry.get("name") or mailbox
        id_token = self._build_id_token(
            mailbox=mailbox, name=name, client_id=client_id, nonce=entry.get("nonce")
        )

        access_token = secrets.token_urlsafe(32)
        await self.cache.set(
            f"oidc:at:{access_token}",
            {"mailbox": mailbox, "name": name},
            TOKEN_TTL,
        )
        return {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": TOKEN_TTL,
            "id_token": id_token,
            "scope": entry.get("scope") or "openid",
        }

    def _build_id_token(
        self, *, mailbox: str, name: str, client_id: str, nonce: str | None
    ) -> str:
        iat = now_ts()
        claims: dict[str, Any] = {
            "iss": self.issuer,
            "sub": mailbox,
            "aud": client_id,
            "azp": client_id,
            "iat": iat,
            "auth_time": iat,
            "exp": iat + ID_TOKEN_TTL,
            **self._identity_claims(mailbox, name),
        }
        if nonce:
            claims["nonce"] = nonce
        return self.signing_key().sign_jwt(claims)

    def _identity_claims(self, mailbox: str, name: str) -> dict[str, Any]:
        return {
            "email": mailbox,
            "email_verified": True,
            "preferred_username": mailbox,
            "name": name or mailbox,
            "mailcow_template": DEFAULT_MAILCOW_TEMPLATE,
        }

    async def userinfo(self, access_token: str) -> dict[str, Any]:
        self._require_configured()
        entry = await self.cache.get(f"oidc:at:{access_token}")
        if not isinstance(entry, dict):
            raise OIDCError(
                "invalid_token", "Access token is invalid or expired.", status_code=401
            )
        mailbox = entry["mailbox"]
        return {"sub": mailbox, **self._identity_claims(mailbox, entry.get("name") or mailbox)}
