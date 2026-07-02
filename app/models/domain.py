from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

DOMAIN_PENDING = "pending"
DOMAIN_VERIFIED = "verified"


def utc_now() -> datetime:
    return datetime.now(UTC)


class Domain(Base):
    """A tenant's custom domain attached to a native (Tetra Engine) app.

    Ownership is proven via a DNS TXT challenge (``token``); only ``verified`` domains
    are routed at the edge and answered by the Caddy on-demand-TLS ask endpoint. A
    hostname is globally unique — one tenant claiming it blocks all others.
    """

    __tablename__ = "domains"
    __table_args__ = (UniqueConstraint("hostname", name="uq_domain_hostname"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), index=True)
    project: Mapped[str] = mapped_column(String(120), index=True)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default=DOMAIN_PENDING, nullable=False)
    token: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    # Cloudflare for SaaS custom-hostname id (ADR 0009); "" when SaaS TLS is disabled.
    cf_hostname_id: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
