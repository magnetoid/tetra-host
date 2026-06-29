import asyncio
from app.db import session_scope, init_db
from app.models import Plan


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
