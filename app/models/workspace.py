"""Workspace hierarchy: team (``Tenant``) → project → environment → app.

Until now a "project" was only a text name repeated on six tables, and an app existed in
three unrelated models (Coolify applications, engine deployments, the catalog). These
tables give every level a real row so the console can address it.

``apps`` is an **index** over the workloads that already exist, not their source of truth:
an engine app points at its stack (``external_id`` = engine project name), a Coolify app
at its application uuid. Service calls keep going through the existing services; the
``WorkloadDriver`` of roadmap phase 3 later builds on the same table. When an app moves
from Coolify to the engine the row stays and only ``driver``/``external_id`` change, so
its placement in the hierarchy survives the migration.
"""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

ENV_PRODUCTION = "production"
ENV_STAGING = "staging"
ENV_PREVIEW = "preview"
ENVIRONMENT_KINDS = (ENV_PRODUCTION, ENV_STAGING, ENV_PREVIEW)

DRIVER_ENGINE = "engine"
DRIVER_COOLIFY = "coolify"
APP_DRIVERS = (DRIVER_ENGINE, DRIVER_COOLIFY)


def utc_now() -> datetime:
    return datetime.now(UTC)


class WorkspaceProject(Base):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("tenant_id", "slug", name="uq_projects_tenant_slug"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), index=True)
    slug: Mapped[str] = mapped_column(String(63), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class Environment(Base):
    __tablename__ = "environments"
    __table_args__ = (UniqueConstraint("project_id", "slug", name="uq_environments_project_slug"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    # Denormalised from the project so every tenant-scoped query filters on one column.
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), index=True)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), index=True)
    slug: Mapped[str] = mapped_column(String(63), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), default=ENV_PRODUCTION, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class WorkspaceApp(Base):
    __tablename__ = "apps"
    __table_args__ = (
        UniqueConstraint("tenant_id", "driver", "external_id", name="uq_apps_tenant_driver_ref"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), index=True)
    environment_id: Mapped[str] = mapped_column(String(36), ForeignKey("environments.id"), index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    driver: Mapped[str] = mapped_column(String(20), nullable=False)
    external_id: Mapped[str] = mapped_column(String(160), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
