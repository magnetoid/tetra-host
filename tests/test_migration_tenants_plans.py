import asyncio

from sqlalchemy import select

from app.db import init_db, session_scope
from app.models import AdminUser, Plan


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
