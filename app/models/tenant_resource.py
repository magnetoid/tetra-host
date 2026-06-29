from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


RESOURCE_TYPE_SITE = "site"
RESOURCE_TYPE_MAIL_DOMAIN = "mail_domain"
RESOURCE_TYPE_MAILBOX = "mailbox"
RESOURCE_TYPE_DNS_ZONE = "dns_zone"
RESOURCE_TYPE_DNS_RECORD = "dns_record"
RESOURCE_TYPE_DATABASE = "database"
RESOURCE_TYPE_SERVER = "server"
RESOURCE_TYPE_APP = "app"

PROVIDER_COOLIFY = "coolify"
PROVIDER_MAILCOW = "mailcow"
PROVIDER_CLOUDFLARE = "cloudflare"
PROVIDER_DOCKER = "docker"


def utc_now() -> datetime:
    return datetime.now(UTC)


class TenantResource(Base):
    __tablename__ = "tenant_resources"
    __table_args__ = (
        Index(
            "ix_tenant_resources_lookup",
            "tenant_id",
            "provider",
            "resource_type",
            "external_id",
            unique=False,
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), index=True)
    provider: Mapped[str] = mapped_column(String(50), index=True)
    resource_type: Mapped[str] = mapped_column(String(50), index=True)
    external_id: Mapped[str] = mapped_column(String(255), index=True)
    display_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    tenant = relationship("Tenant")
