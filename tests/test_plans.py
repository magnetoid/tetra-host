import asyncio
from app.db import session_scope, init_db
from app.models import Plan, Tenant
from app.models.tenant import TENANT_ACTIVE, TENANT_PENDING


def test_plan_round_trips():
    async def go():
        await init_db()
        async with session_scope() as s:
            s.add(Plan(key="free", name="Free", max_apps=1, cpu_millicores=500, mem_mb=512, disk_mb=2048))
        async with session_scope() as s:
            from sqlalchemy import select
            p = (await s.scalars(select(Plan).where(Plan.key == "free"))).one()
            assert p.max_apps == 1 and p.currency == "usd" and p.is_archived is False
    asyncio.run(go())


def test_tenant_is_active_is_derived_from_status():
    t = Tenant(name="X", slug="x", status=TENANT_PENDING)
    assert t.is_active is False
    t.status = TENANT_ACTIVE
    assert t.is_active is True
