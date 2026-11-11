"""add projects, environments, apps (team → project → environment → app hierarchy)

Revision ID: 0005_workspaces
Revises: 0004_import_runs
Create Date: 2026-11-11

New tables only, filled lazily by the workspaces service (engine deployments, previews and
Coolify applications are indexed on first listing). ``create_all`` also creates them on
boot, so each table may already exist when ``alembic upgrade head`` runs; it is skipped then.
An early-model ``projects`` table (no ``slug`` column) is renamed to ``legacy_projects``
first; downgrade does not restore it.
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


LEGACY_PROJECTS = "legacy_projects"


def _set_aside_legacy_projects(bind, existing: set[str]) -> None:
    """Rename an early-model ``projects`` table out of the way, keeping its rows.

    Databases created before multi-tenancy (production among them) carry a
    ``projects`` table with integer ids and Coolify columns that no code reads. It
    has no ``slug`` column, which is how it is told apart from the hierarchy table.
    Its indexes are dropped because SQLite index names are global and the new
    table reuses ``ix_projects_tenant_id``.
    """
    if "projects" not in existing:
        return
    columns = {c["name"] for c in sa.inspect(bind).get_columns("projects")}
    if "slug" in columns:
        return
    for index in sa.inspect(bind).get_indexes("projects"):
        if index["name"]:
            op.drop_index(index["name"], table_name="projects")
    if bind.dialect.name == "sqlite":
        # Keep foreign keys in other tables pointing at the name "projects",
        # which the new table takes over below.
        op.execute("PRAGMA legacy_alter_table=ON")
    op.rename_table("projects", LEGACY_PROJECTS)
    if bind.dialect.name == "sqlite":
        op.execute("PRAGMA legacy_alter_table=OFF")
    existing.discard("projects")
    existing.add(LEGACY_PROJECTS)


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    _set_aside_legacy_projects(bind, existing)
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
