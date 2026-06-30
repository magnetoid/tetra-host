import asyncio

from sqlalchemy import select

from app.db import session_scope
from app.models import AdminUser


def test_bootstrap_admin_is_platform_admin(client):
    async def go():
        async with session_scope() as s:
            admin = (await s.scalars(select(AdminUser).where(AdminUser.email == "admin@example.com"))).first()
            assert admin is not None
            assert admin.role == "platform_admin"

    asyncio.run(go())
