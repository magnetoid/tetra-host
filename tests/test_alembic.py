"""Alembic adoption guardrails.

Tetra Host adopted Alembic on top of a live database whose schema is
materialised by ``Base.metadata.create_all`` plus a legacy in-place upgrader.
The chosen model (see ``alembic/versions/0001_baseline.py``): ``create_all``
builds the latest schema for fresh/test databases and stamps them at ``head``;
existing databases auto-stamp on next boot; genuinely new migrations layer on
the baseline and are applied at deploy time via ``alembic upgrade head``.

These tests lock in the invariants that keep that model safe.
"""

from __future__ import annotations

import asyncio

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from app.db.session import ALEMBIC_INI, _REPO_ROOT, close_db, get_engine, init_db


def _alembic_config() -> Config:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(_REPO_ROOT / "alembic"))
    return config


def test_single_linear_head() -> None:
    """Exactly one head — divergent branches would make ``upgrade head`` ambiguous."""
    heads = ScriptDirectory.from_config(_alembic_config()).get_heads()
    assert len(heads) == 1, f"expected a single Alembic head, found {heads}"


def test_alembic_ini_and_env_present() -> None:
    assert ALEMBIC_INI.exists()
    assert (_REPO_ROOT / "alembic" / "env.py").exists()
    assert (_REPO_ROOT / "alembic" / "versions" / "0001_baseline.py").exists()


def test_init_db_stamps_current_head() -> None:
    """A fresh database is created by ``create_all`` and stamped at the script head."""

    async def _run() -> tuple[list[str], str]:
        await init_db()
        engine = get_engine()
        async with engine.connect() as connection:

            def _read(sync_conn):
                stamped = sync_conn.execute(
                    text("SELECT version_num FROM alembic_version")
                ).fetchall()
                tables = inspect(sync_conn).get_table_names()
                return [row[0] for row in stamped], tables

            return await connection.run_sync(_read)

    stamped, tables = asyncio.run(_run())
    asyncio.run(close_db())

    head = ScriptDirectory.from_config(_alembic_config()).get_current_head()
    assert stamped == [head]
    # The stamp only makes sense if create_all actually built the schema.
    assert "tenants" in tables and "tenant_resources" in tables


def test_init_db_is_idempotent() -> None:
    """Re-running init_db must not double-stamp or raise (every boot calls it)."""

    async def _run() -> int:
        await init_db()
        await init_db()
        engine = get_engine()
        async with engine.connect() as connection:

            def _count(sync_conn):
                return sync_conn.execute(
                    text("SELECT COUNT(*) FROM alembic_version")
                ).scalar()

            return await connection.run_sync(_count)

    count = asyncio.run(_run())
    asyncio.run(close_db())
    assert count == 1


def test_baseline_revision_is_base() -> None:
    """The baseline is the root revision (down_revision is None)."""
    script = ScriptDirectory.from_config(_alembic_config())
    bases = script.get_bases()
    assert "0001_baseline" in bases
