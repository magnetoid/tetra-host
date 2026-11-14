"""add apps.kind and managed_databases.environment_id

Revision ID: 0008_service_kinds
Revises: 0007_managed_databases
Create Date: 2026-11-14

``create_all`` may already have added the columns on a fresh database; each is skipped then.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008_service_kinds"
down_revision: str | None = "0007_managed_databases"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if "kind" not in _columns("apps"):
        with op.batch_alter_table("apps") as batch:
            batch.add_column(sa.Column("kind", sa.String(20), nullable=False, server_default="app"))
    if "environment_id" not in _columns("managed_databases"):
        with op.batch_alter_table("managed_databases") as batch:
            batch.add_column(sa.Column("environment_id", sa.String(36), nullable=True))
        op.create_index(
            "ix_managed_databases_environment_id", "managed_databases", ["environment_id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("managed_databases") as batch:
        batch.drop_index("ix_managed_databases_environment_id")
        batch.drop_column("environment_id")
    with op.batch_alter_table("apps") as batch:
        batch.drop_column("kind")
