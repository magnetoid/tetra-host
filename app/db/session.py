from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

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
    """Legacy in-place migration for databases created before multi-tenancy.

    This only needs to do anything for pre-existing databases that are missing
    the tenant columns. On a freshly created schema the columns already exist
    and there are no legacy rows to backfill, so the default tenant/admin are
    seeded via the ORM in ``ensure_bootstrap_admin`` (which generates a proper
    UUID primary key). We must NOT raw-insert a tenant here: a raw INSERT
    bypasses the model's Python-side ``id`` default and violates the NOT NULL
    primary-key constraint.
    """
    inspector = inspect(connection)
    table_names = set(inspector.get_table_names())
    if "tenants" not in table_names or "admin_users" not in table_names:
        return

    tenant_columns = {column["name"] for column in inspector.get_columns("tenants")}
    if "status" not in tenant_columns:
        connection.execute(text("ALTER TABLE tenants ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active'"))
    if "is_platform_scope" not in tenant_columns:
        connection.execute(text("ALTER TABLE tenants ADD COLUMN is_platform_scope BOOLEAN NOT NULL DEFAULT 0"))

    admin_columns = {column["name"] for column in inspector.get_columns("admin_users")}
    added_tenant_id = "tenant_id" not in admin_columns
    if added_tenant_id:
        connection.execute(text("ALTER TABLE admin_users ADD COLUMN tenant_id VARCHAR(36)"))

    # Only backfill when we just introduced the tenant_id column on a legacy
    # database that already has admins predating multi-tenancy. A freshly
    # created schema short-circuits here and lets the ORM bootstrap seed.
    if not added_tenant_id:
        return

    orphaned = connection.execute(
        text("SELECT COUNT(*) FROM admin_users WHERE tenant_id IS NULL OR tenant_id = ''")
    ).scalar() or 0
    if not orphaned:
        return

    tenant_row = connection.execute(text("SELECT id FROM tenants LIMIT 1")).first()
    if tenant_row is None:
        tenant_id = str(uuid4())
        connection.execute(
            text(
                """
                INSERT INTO tenants (id, name, slug, status, is_platform_scope, created_at, updated_at)
                VALUES (:id, :name, :slug, :status, :is_platform_scope, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
            ),
            {
                "id": tenant_id,
                "name": "Cloud Industry",
                "slug": "cloud-industry",
                "status": "active",
                "is_platform_scope": True,
            },
        )
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
