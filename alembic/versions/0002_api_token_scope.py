"""add scope to api_tokens

Revision ID: 0002_api_token_scope
Revises: 0001_baseline
Create Date: 2026-07-19

The first real migration on top of the baseline: adds ``api_tokens.scope``
(least-privilege read/full). ``api_tokens`` is an existing table on production
(created additively by ``create_all``), so the new column must be added by a
migration — ``create_all`` never ALTERs existing tables. Applied at deploy time
via ``alembic upgrade head``. Fresh/test databases already have the column from
``create_all`` and are stamped at this head, so the migration is a no-op for
them.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_api_token_scope"
down_revision: str | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # batch_alter_table for SQLite compatibility (ALTER ADD COLUMN with a
    # server default; DROP COLUMN in downgrade needs the batch copy).
    with op.batch_alter_table("api_tokens") as batch:
        batch.add_column(
            sa.Column("scope", sa.String(length=10), nullable=False, server_default="full")
        )


def downgrade() -> None:
    with op.batch_alter_table("api_tokens") as batch:
        batch.drop_column("scope")
