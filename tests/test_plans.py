import asyncio
from app.db import session_scope, init_db
from app.models import Plan, Tenant
from app.models.tenant import TENANT_ACTIVE, TENANT_PENDING


def test_plan_round_trips():
    async def go():
        await init_db()
        # init_db now seeds the free plan; just read it back and verify it.
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
