"""add optional TOTP 2FA columns to admin_users

Revision ID: 0003_admin_totp
Revises: 0002_api_token_scope
Create Date: 2026-07-19

Adds opt-in two-factor auth columns to the existing ``admin_users`` table:
``totp_secret``, ``totp_enabled`` (default false — so every existing account
stays 2FA-off and its login is unchanged), and ``totp_backup_codes``. Like
0002, ``create_all`` never ALTERs an existing table, so production picks these
up via ``alembic upgrade head``; fresh/test DBs already have them and are
stamped at this head (no-op).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_admin_totp"
down_revision: str | None = "0002_api_token_scope"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("admin_users") as batch:
        batch.add_column(sa.Column("totp_secret", sa.String(length=64), nullable=True))
        batch.add_column(
            sa.Column("totp_enabled", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch.add_column(sa.Column("totp_backup_codes", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("admin_users") as batch:
        batch.drop_column("totp_backup_codes")
        batch.drop_column("totp_enabled")
        batch.drop_column("totp_secret")
