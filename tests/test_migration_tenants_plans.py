import asyncio

from sqlalchemy import select, text

from app.config import get_settings
from app.db import init_db, session_scope
from app.models import AdminUser, Plan
from app.models.tenant_resource import RESOURCE_TYPE_APP, RESOURCE_TYPE_DNS_ZONE, TenantResource


def test_migration_is_idempotent_and_backfills():
    async def go():
        await init_db()
        await init_db()  # twice = idempotent

        async with session_scope() as s:
            free_plan = (await s.scalars(select(Plan).where(Plan.key == "free"))).first()
            assert free_plan is not None, "free plan must exist after migration"

            admins = (await s.scalars(select(AdminUser))).all()
            # If admins exist, at least one must be platform_admin; empty DB is fine too.
            assert any(a.role == "platform_admin" for a in admins) or len(admins) == 0

    asyncio.run(go())


def test_default_plans_seeded():
    """All three default plans are present with correct resource limits."""

    async def go():
        await init_db()

        async with session_scope() as s:
            plans = {p.key: p for p in (await s.scalars(select(Plan))).all()}

        assert "free" in plans
        assert "pro" in plans
        assert "business" in plans

        free = plans["free"]
        assert free.max_apps == 1
        assert free.max_domains == 0
        assert free.cpu_millicores == 500
        assert free.mem_mb == 512
        assert free.disk_mb == 2048

        pro = plans["pro"]
        assert pro.max_apps == 10
        assert pro.max_domains == 5
        assert pro.cpu_millicores == 8000
        assert pro.mem_mb == 8192
        assert pro.disk_mb == 40960

        biz = plans["business"]
        assert biz.max_apps == 50
        assert biz.max_domains == 25
        assert biz.cpu_millicores == 40000
        assert biz.mem_mb == 65536
        assert biz.disk_mb == 409600

    asyncio.run(go())


def test_allocation_columns_backfilled_for_app_resources():
    """App-type tenant_resources rows get default allocations; non-app rows stay NULL."""

    async def go():
        # First init_db to create all tables.
        await init_db()

        settings = get_settings()

        # Seed a tenant directly so we have a valid tenant_id for foreign-key rows.
        tenant_id = "t-test-alloc-001"
        async with session_scope() as s:
            await s.execute(
                text(
                    "INSERT INTO tenants "
                    "(id, name, slug, status, is_platform_scope, created_at, updated_at) "
                    "VALUES (:id, 'Test Tenant', 'test-alloc', 'active', 0, "
                    "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {"id": tenant_id},
            )

            # Insert directly via raw SQL to simulate legacy rows with NULL allocations.
            await s.execute(
                text(
                    "INSERT INTO tenant_resources "
                    "(id, tenant_id, provider, resource_type, external_id, display_name, "
                    "cpu_millicores, mem_mb, disk_mb, created_at, updated_at) "
                    "VALUES (:id, :tid, 'coolify', :rtype, 'ext-1', 'My App', "
                    "NULL, NULL, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {"id": "tr-app-001", "tid": tenant_id, "rtype": RESOURCE_TYPE_APP},
            )
            await s.execute(
                text(
                    "INSERT INTO tenant_resources "
                    "(id, tenant_id, provider, resource_type, external_id, display_name, "
                    "cpu_millicores, mem_mb, disk_mb, created_at, updated_at) "
                    "VALUES (:id, :tid, 'cloudflare', :rtype, 'ext-2', 'My Zone', "
                    "NULL, NULL, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {"id": "tr-dns-001", "tid": tenant_id, "rtype": RESOURCE_TYPE_DNS_ZONE},
            )

        # Run init_db again (simulates migration on existing DB with legacy rows).
        await init_db()

        async with session_scope() as s:
            app_row = (
                await s.scalars(select(TenantResource).where(TenantResource.id == "tr-app-001"))
            ).first()
            dns_row = (
                await s.scalars(select(TenantResource).where(TenantResource.id == "tr-dns-001"))
            ).first()

        assert app_row is not None
        assert app_row.cpu_millicores == settings.default_app_cpu_millicores
        assert app_row.mem_mb == settings.default_app_mem_mb
        assert app_row.disk_mb == settings.default_app_disk_mb

        assert dns_row is not None
        assert dns_row.cpu_millicores is None, "non-app rows must not get allocation backfill"
        assert dns_row.mem_mb is None
        assert dns_row.disk_mb is None

    asyncio.run(go())
