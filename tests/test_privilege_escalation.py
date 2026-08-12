"""Regression tests for privilege escalation via the startup schema backfill.

`init_db()` runs `_backfill_task14` on EVERY application start. Two of its
statements are unsafe on a deployment that has no seeded platform admin:

  1. "if no platform_admin exists, promote the oldest admin_user" — on a panel
     where `ADMIN_BOOTSTRAP_PASSWORD` is unset (or the seed account was removed),
     the oldest admin_user is the FIRST SELF-SERVE SIGNUP. A restart hands that
     unvetted account the platform_admin role.
  2. "mark every platform admin's tenant is_platform_scope=1" — which makes
     `TenantResourceFilter._fall_open()` return True for that tenant, i.e. it
     sees every other tenant's sites, DNS, mail, databases and servers.

Neither promotion may ever select a self-serve tenant.
"""

import asyncio

from sqlalchemy import select

from app.db import init_db, session_scope
from app.models import AdminUser, Tenant
from app.models.admin import ROLE_PLATFORM_ADMIN


def _signup(client, email: str, org: str) -> None:
    response = client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "correct-horse-battery", "org_name": org},
    )
    assert response.status_code == 200, response.text
    assert response.json()["admin"]["id"], "signup should have created an admin"


async def _drop_seeded_platform_admins() -> None:
    """Simulate a deployment with no seeded platform admin (ADMIN_BOOTSTRAP_PASSWORD
    unset, or the seed account since removed)."""
    async with session_scope() as session:
        seeded = (
            await session.scalars(
                select(AdminUser).where(AdminUser.role == ROLE_PLATFORM_ADMIN)
            )
        ).all()
        for admin in seeded:
            await session.delete(admin)


async def _reload(email: str) -> tuple[AdminUser, Tenant]:
    async with session_scope() as session:
        admin = (
            await session.scalars(select(AdminUser).where(AdminUser.email == email))
        ).one()
        tenant = (
            await session.scalars(select(Tenant).where(Tenant.id == admin.tenant_id))
        ).one()
        return admin, tenant


def test_restart_does_not_promote_self_serve_signup_to_platform_admin(client):
    """A self-serve signup must not gain platform_admin on the next restart."""

    _signup(client, "attacker@evil.example", "Evil Corp")

    async def go():
        await _drop_seeded_platform_admins()

        # A restart: lifespan calls init_db(), which re-runs the backfills.
        await init_db()

        admin, tenant = await _reload("attacker@evil.example")
        assert admin.role != ROLE_PLATFORM_ADMIN, (
            "PRIVILEGE ESCALATION: the first self-serve signup was promoted to "
            "platform_admin by the startup backfill"
        )
        assert tenant.is_platform_scope is False, (
            "TENANT ISOLATION BREAK: the self-serve tenant was marked platform-scope, "
            "so TenantResourceFilter falls open and it can read every other tenant"
        )

    asyncio.run(go())


def test_restart_does_not_platform_scope_a_self_serve_tenant(client):
    """Even with several signups, no self-serve tenant may become platform-scope."""

    _signup(client, "first@evil.example", "First Corp")
    _signup(client, "second@evil.example", "Second Corp")

    async def go():
        await _drop_seeded_platform_admins()
        await init_db()

        for email in ("first@evil.example", "second@evil.example"):
            admin, tenant = await _reload(email)
            assert admin.role != ROLE_PLATFORM_ADMIN, f"{email} was promoted"
            assert tenant.is_platform_scope is False, f"{email}'s tenant fell open"

    asyncio.run(go())
