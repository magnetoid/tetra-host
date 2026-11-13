"""add managed_databases and database_backups

Revision ID: 0007_managed_databases
Revises: 0006_drop_coolify_rows
Create Date: 2026-11-13

New tables only. ``create_all`` also creates them on boot, so each may already exist when
``alembic upgrade head`` runs; it is skipped then.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_managed_databases"
down_revision: str | None = "0006_drop_coolify_rows"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "managed_databases" not in existing:
        op.create_table(
            "managed_databases",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), nullable=False),
            sa.Column("name", sa.String(63), nullable=False),
            sa.Column("engine", sa.String(20), nullable=False),
            sa.Column("version", sa.String(20), nullable=False, server_default=""),
            sa.Column("project", sa.String(63), nullable=False, unique=True),
            sa.Column("secret", sa.Text(), nullable=False, server_default=""),
            sa.Column("backup_cron", sa.String(120), nullable=False, server_default="0 3 * * *"),
            sa.Column("backup_keep", sa.Integer(), nullable=False, server_default="7"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("tenant_id", "name", name="uq_managed_db_tenant_name"),
        )
        op.create_index("ix_managed_databases_tenant_id", "managed_databases", ["tenant_id"])
    if "database_backups" not in existing:
        op.create_table(
            "database_backups",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("database_id", sa.String(36), nullable=False),
            sa.Column("tenant_id", sa.String(36), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="running"),
            sa.Column("trigger", sa.String(20), nullable=False, server_default="manual"),
            sa.Column("filename", sa.String(500), nullable=False, server_default=""),
            sa.Column("size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("error", sa.String(500), nullable=False, server_default=""),
            sa.Column("restore_status", sa.String(20), nullable=False, server_default=""),
            sa.Column("restore_error", sa.String(500), nullable=False, server_default=""),
            sa.Column("restored_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_database_backups_database_id", "database_backups", ["database_id"])
        op.create_index("ix_database_backups_tenant_id", "database_backups", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("database_backups")
    op.drop_table("managed_databases")
