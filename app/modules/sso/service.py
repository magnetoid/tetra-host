"""OpenID Connect single sign-on service.

Per-tenant OIDC: an owner registers their IdP (issuer + client credentials +
allowed email domains); members then sign in through the IdP and are
JIT-provisioned into the tenant.

Flow (Authorization Code):
  1. build_authorize_url() — discover the IdP, sign a short-lived state that
     binds the tenant + redirect_uri (stateless CSRF token), return the IdP
     authorize URL.
  2. handle_callback() — verify state, exchange the code for tokens directly
     with the IdP over TLS, read the verified email from the userinfo endpoint,
     enforce the domain allowlist, find-or-create the member, return them.

Email trust: tokens and userinfo are fetched server-to-server directly from the
discovered IdP endpoints over TLS, so the returned email is authentic. Full
id_token JWKS signature validation is a planned hardening follow-up.
"""

import logging
import secrets as secretslib

import httpx
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import AdminUser, Tenant, TenantSSOConfig
from app.models.tenant import TENANT_ACTIVE
from app.modules.auth.service import AuthService
from app.services import secrets as secret_box
from app.services.http import ProviderAPIError, request_json

logger = logging.getLogger(__name__)

SSO_STATE_SALT = "tetra-sso-state"
STATE_MAX_AGE_SECONDS = 600  # 10 minutes to complete the round-trip.
DISCOVERY_TIMEOUT = 10.0

# Process-lifetime cache of discovery documents (issuer → doc). OIDC discovery
# metadata is effectively static; a restart re-fetches.
_discovery_cache: dict[str, dict] = {}


class SSOError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class SSOService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.auth = AuthService(session)

    # ── Config CRUD (owner-facing) ───────────────────────────────────────
    async def get_config(self, tenant_id: str) -> TenantSSOConfig | None:
        result = await self.session.execute(
            select(TenantSSOConfig).where(TenantSSOConfig.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def upsert_config(
        self,
        tenant_id: str,
        *,
        issuer: str,
        client_id: str,
        client_secret: str | None,
        allowed_domains: str,
        default_role: str,
        provider_label: str,
        enabled: bool,
    ) -> TenantSSOConfig:
        issuer = (issuer or "").strip().rstrip("/")
        if enabled and (not issuer or not client_id):
            raise SSOError("Issuer and client ID are required to enable SSO.")
        if default_role not in {"member", "admin"}:
            raise SSOError("Default role must be 'member' or 'admin'.")

        config = await self.get_config(tenant_id)
        if config is None:
            config = TenantSSOConfig(tenant_id=tenant_id)
            self.session.add(config)

        config.issuer = issuer
        config.client_id = client_id.strip()
        # Only overwrite the secret when a new one is supplied (blank = keep existing).
        if client_secret:
            config.client_secret_enc = secret_box.encrypt(client_secret)
        config.allowed_domains = (allowed_domains or "").strip()
        config.default_role = default_role
        config.provider_label = (provider_label or "OpenID Connect").strip()
        config.enabled = enabled
        await self.session.flush()
        logger.info(
            "SSO config saved for tenant %s (issuer %s, enabled=%s)",
            tenant_id, issuer or "unset", enabled,
        )
        return config

    async def delete_config(self, tenant_id: str) -> None:
        config = await self.get_config(tenant_id)
        if config is not None:
            await self.session.delete(config)
            await self.session.flush()
            logger.info("SSO config deleted for tenant %s", tenant_id)

    # ── OIDC flow ────────────────────────────────────────────────────────
    def _serializer(self, settings: Settings) -> URLSafeTimedSerializer:
        return URLSafeTimedSerializer(settings.app_secret, salt=SSO_STATE_SALT)

    async def _discover(self, issuer: str) -> dict:
        if issuer in _discovery_cache:
            return _discovery_cache[issuer]
        url = f"{issuer}/.well-known/openid-configuration"
        async with httpx.AsyncClient(timeout=DISCOVERY_TIMEOUT) as client:
            try:
                doc = await request_json(client, service="OIDC", method="GET", url=url)
            except ProviderAPIError as exc:
                logger.warning("OIDC discovery failed for issuer %s", issuer)
                raise SSOError("Could not reach the identity provider.", status_code=502) from exc
        if not isinstance(doc, dict) or "authorization_endpoint" not in doc:
            raise SSOError("Identity provider returned an invalid discovery document.", status_code=502)
        _discovery_cache[issuer] = doc
        return doc

    async def _enabled_config_for_slug(self, slug: str) -> tuple[Tenant, TenantSSOConfig]:
        tenant = await self.auth.get_tenant_by_slug(slug)
        if tenant is None:
            raise SSOError("Unknown workspace.", status_code=404)
        config = await self.get_config(tenant.id)
        if config is None or not config.enabled:
            raise SSOError("Single sign-on is not enabled for this workspace.", status_code=404)
        return tenant, config

    async def build_authorize_url(
        self, settings: Settings, slug: str, redirect_uri: str
    ) -> str:
        if not redirect_uri.startswith("https://") and not redirect_uri.startswith("http://"):
            raise SSOError("Invalid redirect URI.")
        tenant, config = await self._enabled_config_for_slug(slug)
        doc = await self._discover(config.issuer)

        # Stateless CSRF: sign the tenant + redirect_uri + a nonce. Verified on callback.
        nonce = secretslib.token_urlsafe(16)
        state = self._serializer(settings).dumps(
            {"t": tenant.id, "r": redirect_uri, "n": nonce}
        )
        params = httpx.QueryParams(
            {
                "response_type": "code",
                "client_id": config.client_id,
                "redirect_uri": redirect_uri,
                "scope": "openid email profile",
                "state": state,
                "nonce": nonce,
            }
        )
        return f"{doc['authorization_endpoint']}?{params}"

    async def handle_callback(
        self, settings: Settings, code: str, state: str, redirect_uri: str
    ) -> AdminUser:
        if not code or not state:
            raise SSOError("Missing authorization code.")
        try:
            payload = self._serializer(settings).loads(state, max_age=STATE_MAX_AGE_SECONDS)
        except SignatureExpired as exc:
            raise SSOError("Sign-in took too long — please try again.", status_code=400) from exc
        except BadSignature as exc:
            raise SSOError("Invalid sign-in state.", status_code=400) from exc

        tenant_id = payload.get("t")
        if payload.get("r") != redirect_uri:
            raise SSOError("Redirect URI mismatch.", status_code=400)

        config = await self.get_config(tenant_id)
        if config is None or not config.enabled:
            raise SSOError("Single sign-on is not enabled.", status_code=404)
        tenant = await self.session.get(Tenant, tenant_id)
        if tenant is None or tenant.status != TENANT_ACTIVE:
            raise SSOError("Workspace is not active.", status_code=403)

        doc = await self._discover(config.issuer)
        client_secret = secret_box.decrypt(config.client_secret_enc)

        async with httpx.AsyncClient(timeout=DISCOVERY_TIMEOUT) as client:
            try:
                tokens = await request_json(
                    client,
                    service="OIDC",
                    method="POST",
                    url=doc["token_endpoint"],
                    headers={"Accept": "application/json"},
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": redirect_uri,
                        "client_id": config.client_id,
                        "client_secret": client_secret,
                    },
                    max_attempts=1,
                )
            except ProviderAPIError as exc:
                logger.warning("OIDC token exchange failed (tenant %s)", tenant_id)
                raise SSOError("The identity provider rejected the sign-in.", status_code=401) from exc

            access_token = (tokens or {}).get("access_token")
            if not access_token:
                raise SSOError("The identity provider did not return a token.", status_code=401)

            try:
                userinfo = await request_json(
                    client,
                    service="OIDC",
                    method="GET",
                    url=doc["userinfo_endpoint"],
                    headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
                    max_attempts=1,
                )
            except ProviderAPIError as exc:
                raise SSOError("Could not read your profile from the provider.", status_code=502) from exc

        email = self.auth.normalize_email(str((userinfo or {}).get("email") or ""))
        email_verified = (userinfo or {}).get("email_verified")
        if not email or "@" not in email:
            raise SSOError("The identity provider did not return an email.", status_code=401)
        if email_verified is False:
            raise SSOError("Your email is not verified with the identity provider.", status_code=403)

        domains = config.allowed_domain_list()
        if domains and email.split("@", 1)[1] not in domains:
            raise SSOError("Your email domain is not permitted for this workspace.", status_code=403)

        return await self._provision(tenant, config, email, str((userinfo or {}).get("name") or ""))

    async def _provision(
        self, tenant: Tenant, config: TenantSSOConfig, email: str, name: str
    ) -> AdminUser:
        existing = await self.auth.get_admin_by_email(email)
        if existing is not None:
            if existing.tenant_id != tenant.id:
                raise SSOError("That email is already registered to another workspace.", status_code=409)
            if not existing.is_active:
                raise SSOError("Your account has been deactivated.", status_code=403)
            return existing

        # JIT provision. SSO users have no usable password (random hash); they can
        # only sign in through the IdP.
        admin = AdminUser(
            tenant_id=tenant.id,
            email=email,
            full_name=name.strip() or email,
            password_hash=self.auth.hash_password(secretslib.token_urlsafe(32)),
            is_active=True,
            role=config.default_role,
        )
        self.session.add(admin)
        await self.session.flush()
        logger.info(
            "SSO member %s provisioned in tenant %s (role %s)",
            admin.id, tenant.id, config.default_role,
        )
        return await self.auth.get_admin_by_id(admin.id)
