from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db.base import Base


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine, _session_factory
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.app_env == "development",
            future=True,
            pool_pre_ping=True,
        )
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        get_engine()
    assert _session_factory is not None
    return _session_factory


async def init_db() -> None:
    import app.models  # noqa: F401

    async with get_engine().begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.run_sync(_upgrade_existing_schema)


def _upgrade_existing_schema(connection) -> None:
    inspector = inspect(connection)
    table_names = set(inspector.get_table_names())
    if "tenants" not in table_names or "admin_users" not in table_names:
        return

    tenant_columns = {column["name"] for column in inspector.get_columns("tenants")}
    if "is_active" not in tenant_columns:
        connection.execute(text("ALTER TABLE tenants ADD COLUMN is_active BOOLEAN DEFAULT 1"))

    admin_columns = {column["name"] for column in inspector.get_columns("admin_users")}
    if "tenant_id" not in admin_columns:
        connection.execute(text("ALTER TABLE admin_users ADD COLUMN tenant_id VARCHAR(36)"))

    tenant_row = connection.execute(
        text("SELECT id FROM tenants LIMIT 1")
    ).first()
    if tenant_row is None:
        connection.execute(
            text(
                """
                INSERT INTO tenants (name, slug, is_active, created_at, updated_at)
                VALUES (:name, :slug, :is_active, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
            ),
            {
                "name": "Cloud Industry",
                "slug": "cloud-industry",
                "is_active": True,
            },
        )
        tenant_id = connection.execute(
            text("SELECT id FROM tenants WHERE slug = 'cloud-industry' LIMIT 1")
        ).scalar()
    else:
        tenant_id = tenant_row[0]

    connection.execute(
        text("UPDATE admin_users SET tenant_id = :tenant_id WHERE tenant_id IS NULL OR tenant_id = ''"),
        {"tenant_id": tenant_id},
    )


async def close_db() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    session = get_session_factory()()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with session_scope() as session:
        yield session
