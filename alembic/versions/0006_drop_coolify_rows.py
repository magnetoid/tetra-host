"""drop Coolify rows: the panel no longer manages apps through Coolify

Revision ID: 0006_drop_coolify_rows
Revises: 0005_workspaces
Create Date: 2026-11-11

Data only. Coolify is an import source now (ADR 0018), not something the panel manages, so
tenant assignments of Coolify sites, databases and servers (``tenant_resources`` with
provider ``coolify``) and hierarchy rows indexing Coolify apps (``apps`` with driver
``coolify``) have nothing left to point at. Import history (``import_runs``) is kept.

Downgrade is a no-op: the deleted rows are not recreated. Back up the database first.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_drop_coolify_rows"
down_revision: str | None = "0005_workspaces"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "apps" in tables:
        op.execute(sa.text("DELETE FROM apps WHERE driver = 'coolify'"))
    if "tenant_resources" in tables:
        op.execute(sa.text("DELETE FROM tenant_resources WHERE provider = 'coolify'"))


def downgrade() -> None:
    pass
