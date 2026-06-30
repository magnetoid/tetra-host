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

    def get_columns(table: str) -> set[str]:
        return {col["name"] for col in inspector.get_columns(table)}

    tenant_columns = get_columns("tenants")
    if "status" not in tenant_columns:
        connection.execute(text("ALTER TABLE tenants ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active'"))
    if "is_platform_scope" not in tenant_columns:
        connection.execute(text("ALTER TABLE tenants ADD COLUMN is_platform_scope BOOLEAN NOT NULL DEFAULT 0"))

    admin_columns = get_columns("admin_users")
    added_tenant_id = "tenant_id" not in admin_columns
    if added_tenant_id:
        connection.execute(text("ALTER TABLE admin_users ADD COLUMN tenant_id VARCHAR(36)"))

    # --- Task 1.4: plan_id column on tenants ---
    # Re-inspect after any ALTERs above so our column set is fresh.
    tenant_columns = get_columns("tenants")
    if "plan_id" not in tenant_columns:
        connection.execute(text("ALTER TABLE tenants ADD COLUMN plan_id VARCHAR(36)"))

    # --- signup_ip column on tenants (per-IP pending-cap anti-abuse) ---
    tenant_columns = get_columns("tenants")
    if "signup_ip" not in tenant_columns:
        connection.execute(text("ALTER TABLE tenants ADD COLUMN signup_ip VARCHAR(64)"))

    # --- Task 1.4: role column on admin_users ---
    admin_columns = get_columns("admin_users")
    if "role" not in admin_columns:
        connection.execute(text("ALTER TABLE admin_users ADD COLUMN role VARCHAR(20) DEFAULT 'owner'"))

    # --- Task 1.4: seed default plans (idempotent on key) ---
    if "plans" in table_names:
        _seed_default_plans(connection)

    # --- Task 3.1: allocation columns on tenant_resources ---
    if "tenant_resources" in table_names:
        tr_columns = get_columns("tenant_resources")
        if "cpu_millicores" not in tr_columns:
            connection.execute(text("ALTER TABLE tenant_resources ADD COLUMN cpu_millicores INTEGER"))
        if "mem_mb" not in tr_columns:
            connection.execute(text("ALTER TABLE tenant_resources ADD COLUMN mem_mb INTEGER"))
        if "disk_mb" not in tr_columns:
            connection.execute(text("ALTER TABLE tenant_resources ADD COLUMN disk_mb INTEGER"))
        _backfill_task31(connection)

    # Only backfill when we just introduced the tenant_id column on a legacy
    # database that already has admins predating multi-tenancy. A freshly
    # created schema short-circuits here and lets the ORM bootstrap seed.
    if not added_tenant_id:
        # Still run Task 1.4 backfills even on non-legacy DBs.
        _backfill_task14(connection)
        return

    orphaned = connection.execute(
        text("SELECT COUNT(*) FROM admin_users WHERE tenant_id IS NULL OR tenant_id = ''")
    ).scalar() or 0
    if not orphaned:
        _backfill_task14(connection)
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

    _backfill_task14(connection)


def _seed_default_plans(connection) -> None:
    """Seed the three built-in plans if they don't already exist (idempotent on key)."""
    plans = [
        {
            "key": "free",
            "name": "Free",
            "max_apps": 1,
            "max_domains": 0,
            "cpu_millicores": 500,
            "mem_mb": 512,
            "disk_mb": 2048,
            "sort_order": 0,
        },
        {
            "key": "pro",
            "name": "Pro",
            "max_apps": 10,
            "max_domains": 5,
            "cpu_millicores": 8000,
            "mem_mb": 8192,
            "disk_mb": 40960,
            "sort_order": 1,
        },
        {
            "key": "business",
            "name": "Business",
            "max_apps": 50,
            "max_domains": 25,
            "cpu_millicores": 40000,
            "mem_mb": 65536,
            "disk_mb": 409600,
            "sort_order": 2,
        },
    ]
    for plan in plans:
        existing = connection.execute(
            text("SELECT id FROM plans WHERE key = :key"),
            {"key": plan["key"]},
        ).first()
        if existing is None:
            connection.execute(
                text(
                    """
                    INSERT INTO plans (
                        id, key, name, description, price_cents, currency, stripe_price_id,
                        max_apps, max_domains, cpu_millicores, mem_mb, disk_mb,
                        is_archived, sort_order, created_at, updated_at
                    ) VALUES (
                        :id, :key, :name, '', 0, 'usd', '',
                        :max_apps, :max_domains, :cpu_millicores, :mem_mb, :disk_mb,
                        0, :sort_order, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    """
                ),
                {"id": str(uuid4()), **plan},
            )


def _backfill_task14(connection) -> None:
    """Backfill status, plan_id, is_platform_scope, and admin role (idempotent)."""
    inspector = inspect(connection)
    tenant_columns = {col["name"] for col in inspector.get_columns("tenants")}

    # Backfill status from legacy is_active only if the legacy column still exists.
    if "is_active" in tenant_columns:
        connection.execute(
            text("UPDATE tenants SET status='suspended' WHERE is_active = 0 AND status='active'")
        )

    # Mark the default/bootstrap tenant as platform scope.
    connection.execute(text("UPDATE tenants SET is_platform_scope=1 WHERE slug='default'"))

    # Backfill plan_id to free for tenants without a plan.
    connection.execute(
        text(
            "UPDATE tenants SET plan_id=(SELECT id FROM plans WHERE key='free') WHERE plan_id IS NULL"
        )
    )

    # Role backfill: set bootstrap admin email to platform_admin.
    bootstrap_email = get_settings().admin_bootstrap_email.strip().lower()
    connection.execute(
        text("UPDATE admin_users SET role='platform_admin' WHERE lower(email)=:e"),
        {"e": bootstrap_email},
    )

    # Ensure at least one platform_admin exists; if none, promote the oldest.
    count = connection.execute(
        text("SELECT COUNT(*) FROM admin_users WHERE role='platform_admin'")
    ).scalar() or 0
    if not count:
        connection.execute(
            text(
                "UPDATE admin_users SET role='platform_admin' "
                "WHERE id=(SELECT id FROM admin_users ORDER BY created_at LIMIT 1)"
            )
        )

    # Mark every platform admin's tenant as platform-scope. The legacy/platform tenant
    # (which owns all pre-multi-tenancy global resources) must fall open in the
    # fail-closed isolation filter, or its admin would see an empty panel. This covers
    # production tenants whose slug isn't 'default' (e.g. 'cloud-industry'). Runs AFTER
    # the role backfill so the platform_admin rows are set. Idempotent.
    connection.execute(
        text(
            "UPDATE tenants SET is_platform_scope=1 "
            "WHERE id IN (SELECT DISTINCT tenant_id FROM admin_users WHERE role='platform_admin')"
        )
    )


def _backfill_task31(connection) -> None:
    """Backfill cpu_millicores/mem_mb/disk_mb on app-type tenant_resources (idempotent: NULL-only)."""
    settings = get_settings()
    connection.execute(
        text(
            "UPDATE tenant_resources "
            "SET cpu_millicores=:c, mem_mb=:m, disk_mb=:d "
            "WHERE resource_type='app' AND cpu_millicores IS NULL"
        ),
        {
            "c": settings.default_app_cpu_millicores,
            "m": settings.default_app_mem_mb,
            "d": settings.default_app_disk_mb,
        },
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
