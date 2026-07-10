from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class TenantSSOConfig(Base):
    """Per-tenant OpenID Connect single sign-on configuration.

    One row per tenant. The client secret is stored encrypted at rest (Fernet,
    keyed off APP_SECRET — see app/services/secrets.py); it is never returned to
    clients. Members whose email matches ``allowed_domains`` are JIT-provisioned
    into the tenant with ``default_role`` on first SSO login.
    """

    __tablename__ = "tenant_sso_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), unique=True, index=True
    )
    provider_label: Mapped[str] = mapped_column(String(80), default="OpenID Connect")
    # OIDC issuer base URL — its /.well-known/openid-configuration is discovered.
    issuer: Mapped[str] = mapped_column(String(500), default="")
    client_id: Mapped[str] = mapped_column(String(255), default="")
    client_secret_enc: Mapped[str] = mapped_column(String(1000), default="")
    # Comma-separated email domains allowed to JIT-provision, e.g. "acme.com,acme.io".
    # Empty = allow any email the IdP returns (owner opted into an open IdP).
    allowed_domains: Mapped[str] = mapped_column(String(500), default="")
    default_role: Mapped[str] = mapped_column(String(20), default="member")
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    def allowed_domain_list(self) -> list[str]:
        return [d.strip().lower() for d in (self.allowed_domains or "").split(",") if d.strip()]
