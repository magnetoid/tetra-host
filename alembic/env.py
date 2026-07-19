"""Alembic migration environment for Tetra Host.

This file supports two invocation modes:

* **CLI** (``alembic upgrade head`` / ``alembic revision --autogenerate``): it
  builds its own async engine from the application ``Settings`` so migrations
  always target the same ``DATABASE_URL`` (and async-driver normalisation) as
  the running app.
* **In-process**: application code may pass a live SQLAlchemy connection via
  ``config.attributes["connection"]`` to reuse the app's engine/transaction.
  (The app's normal path is the lightweight stamp in ``app.db.session`` — this
  hook exists for completeness and for tooling that wants a shared connection.)

``target_metadata`` is the app's declarative ``Base.metadata`` with every model
imported, so ``--autogenerate`` sees the full schema.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

import app.models  # noqa: F401  — registers every table on Base.metadata
from app.config import get_settings
from app.db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    # Read at call time so tests / env overrides are respected.
    return get_settings().database_url


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a DB connection (``alembic upgrade --sql``)."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def _run_async_migrations() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _database_url()
    connectable = async_engine_from_config(
        configuration, prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        _do_run_migrations(connection)
    else:
        asyncio.run(_run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
