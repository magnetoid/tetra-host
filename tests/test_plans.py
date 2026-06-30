import asyncio

from app.db import session_scope, init_db
from app.models import Plan, Tenant
from app.models.admin import ROLE_OWNER
from app.models.tenant import TENANT_ACTIVE, TENANT_PENDING
from app.modules.auth.service import AuthService


# ---------------------------------------------------------------------------
# Existing model tests (preserved)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _seed_owner_for_plans() -> None:
    async with session_scope() as session:
        auth_service = AuthService(session)
        tenant = Tenant(name="Plans Owner Tenant", slug="planownertenant", status="active")
        session.add(tenant)
        await session.flush()
        from app.models import AdminUser
        session.add(
            AdminUser(
                tenant_id=tenant.id,
                email="plansowner@x.test",
                full_name="Plans Owner",
                password_hash=auth_service.hash_password("plans-pw"),
                is_active=True,
                role=ROLE_OWNER,
            )
        )


def _login_as(client, email: str, password: str) -> dict[str, str]:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['token']}"}


# ---------------------------------------------------------------------------
# Task 1.6: Plan CRUD API tests
# ---------------------------------------------------------------------------

def test_owner_can_list_plans(client):
    """Any authenticated admin can GET /api/v1/plans (read is open to all admins)."""
    asyncio.run(_seed_owner_for_plans())
    headers = _login_as(client, "plansowner@x.test", "plans-pw")
    resp = client.get("/api/v1/plans", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    # seeded plans (free/pro/business) should be present
    assert isinstance(body, list)
    keys = [p["key"] for p in body]
    assert "free" in keys


def test_owner_cannot_create_plan(client):
    """Owner role must receive 403 on POST /api/v1/plans."""
    asyncio.run(_seed_owner_for_plans())
    headers = _login_as(client, "plansowner@x.test", "plans-pw")
    resp = client.post(
        "/api/v1/plans",
        headers=headers,
        json={
            "key": "enterprise",
            "name": "Enterprise",
            "max_apps": 200,
            "max_domains": 200,
            "cpu_millicores": 100000,
            "mem_mb": 204800,
            "disk_mb": 1048576,
        },
    )
    assert resp.status_code == 403


def test_platform_admin_can_create_plan_and_list_it(client):
    """Platform admin can POST /api/v1/plans and the new plan appears in GET."""
    headers = _login_as(client, "admin@example.com", "supersecurepassword")

    payload = {
        "key": "enterprise",
        "name": "Enterprise",
        "max_apps": 200,
        "max_domains": 200,
        "cpu_millicores": 200000,
        "mem_mb": 204800,
        "disk_mb": 1048576,
        "sort_order": 99,
    }
    create_resp = client.post("/api/v1/plans", headers=headers, json=payload)
    assert create_resp.status_code == 200, create_resp.text

    body = create_resp.json()
    assert body["key"] == "enterprise"
    assert body["name"] == "Enterprise"
    assert body["max_apps"] == 200

    # Now list and confirm it appears
    list_resp = client.get("/api/v1/plans", headers=headers)
    assert list_resp.status_code == 200
    keys = [p["key"] for p in list_resp.json()]
    assert "enterprise" in keys


def test_create_plan_validation_422(client):
    """POST with incoherent max_apps × cpu_millicores must return 422."""
    headers = _login_as(client, "admin@example.com", "supersecurepassword")
    # max_apps=100, cpu_millicores=500 → 100*500=50000 > 500 → invalid
    resp = client.post(
        "/api/v1/plans",
        headers=headers,
        json={
            "key": "bad-plan",
            "name": "Bad Plan",
            "max_apps": 100,
            "max_domains": 10,
            "cpu_millicores": 500,
            "mem_mb": 204800,
            "disk_mb": 1048576,
        },
    )
    assert resp.status_code == 422


def test_platform_admin_can_update_plan(client):
    """PATCH /api/v1/plans/{plan_id} updates a plan field."""
    headers = _login_as(client, "admin@example.com", "supersecurepassword")

    # Read the free plan
    list_resp = client.get("/api/v1/plans", headers=headers)
    free = next(p for p in list_resp.json() if p["key"] == "free")
    plan_id = free["id"]

    patch_resp = client.patch(
        f"/api/v1/plans/{plan_id}",
        headers=headers,
        json={"name": "Free Updated"},
    )
    assert patch_resp.status_code == 200, patch_resp.text
    assert patch_resp.json()["name"] == "Free Updated"


def test_owner_cannot_update_plan(client):
    """Owner must receive 403 on PATCH /api/v1/plans/{plan_id}."""
    asyncio.run(_seed_owner_for_plans())
    headers_admin = _login_as(client, "admin@example.com", "supersecurepassword")
    list_resp = client.get("/api/v1/plans", headers=headers_admin)
    free = next(p for p in list_resp.json() if p["key"] == "free")
    plan_id = free["id"]

    headers_owner = _login_as(client, "plansowner@x.test", "plans-pw")
    resp = client.patch(
        f"/api/v1/plans/{plan_id}",
        headers=headers_owner,
        json={"name": "Hacked"},
    )
    assert resp.status_code == 403


def test_platform_admin_can_archive_plan(client):
    """POST /api/v1/plans/{plan_id}/archive marks plan as archived."""
    headers = _login_as(client, "admin@example.com", "supersecurepassword")

    # Create a plan to archive
    create_resp = client.post(
        "/api/v1/plans",
        headers=headers,
        json={
            "key": "to-archive",
            "name": "Archive Me",
            "max_apps": 1,
            "max_domains": 1,
            "cpu_millicores": 500,
            "mem_mb": 512,
            "disk_mb": 2048,
        },
    )
    assert create_resp.status_code == 200
    plan_id = create_resp.json()["id"]

    archive_resp = client.post(f"/api/v1/plans/{plan_id}/archive", headers=headers)
    assert archive_resp.status_code == 200, archive_resp.text
    assert archive_resp.json()["is_archived"] is True

    # Default list (include_archived=false) should not include it
    list_resp = client.get("/api/v1/plans", headers=headers)
    ids = [p["id"] for p in list_resp.json()]
    assert plan_id not in ids

    # With include_archived=true it should appear
    list_all_resp = client.get("/api/v1/plans?include_archived=true", headers=headers)
    ids_all = [p["id"] for p in list_all_resp.json()]
    assert plan_id in ids_all
