"""add import_runs (Coolify/Plesk → Tetra Engine migrations)

Revision ID: 0004_import_runs
Revises: 0003_admin_totp
Create Date: 2026-11-10

New table only. ``create_all`` also creates it on boot, so the table may already exist
when ``alembic upgrade head`` runs on a database that booted the new code first; the
upgrade is a no-op in that case.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_import_runs"
down_revision: str | None = "0003_admin_totp"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if "import_runs" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "import_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), nullable=False, index=True),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("source_ref", sa.String(length=128), nullable=False, index=True),
        sa.Column("project", sa.String(length=63), nullable=False, index=True),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("secret_blob", sa.Text(), nullable=False),
        sa.Column("log", sa.Text(), nullable=False),
        sa.Column("error", sa.String(length=1000), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("import_runs")
