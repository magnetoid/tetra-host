"""add projects, environments, apps (team → project → environment → app hierarchy)

Revision ID: 0005_workspaces
Revises: 0004_import_runs
Create Date: 2026-11-11

New tables only, filled lazily by the workspaces service (engine deployments, previews and
Coolify applications are indexed on first listing). ``create_all`` also creates them on
boot, so each table may already exist when ``alembic upgrade head`` runs; it is skipped then.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_workspaces"
down_revision: str | None = "0004_import_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "projects" not in existing:
        op.create_table(
            "projects",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"),
                      nullable=False, index=True),
            sa.Column("slug", sa.String(length=63), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            *_timestamps(),
            sa.UniqueConstraint("tenant_id", "slug", name="uq_projects_tenant_slug"),
        )
    if "environments" not in existing:
        op.create_table(
            "environments",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"),
                      nullable=False, index=True),
            sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id"),
                      nullable=False, index=True),
            sa.Column("slug", sa.String(length=63), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("kind", sa.String(length=20), nullable=False),
            *_timestamps(),
            sa.UniqueConstraint("project_id", "slug", name="uq_environments_project_slug"),
        )
    if "apps" not in existing:
        op.create_table(
            "apps",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"),
                      nullable=False, index=True),
            sa.Column("environment_id", sa.String(length=36), sa.ForeignKey("environments.id"),
                      nullable=False, index=True),
            sa.Column("name", sa.String(length=160), nullable=False),
            sa.Column("driver", sa.String(length=20), nullable=False),
            sa.Column("external_id", sa.String(length=160), nullable=False),
            sa.Column("domain", sa.String(length=255), nullable=False),
            *_timestamps(),
            sa.UniqueConstraint("tenant_id", "driver", "external_id",
                                name="uq_apps_tenant_driver_ref"),
        )


def downgrade() -> None:
    op.drop_table("apps")
    op.drop_table("environments")
    op.drop_table("projects")
