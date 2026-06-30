"""GET /api/v1/admin/overview — the super-admin command-center aggregate.

Verifies the platform-admin gate (401 unauth / 403 owner / 200 platform_admin),
the response shape, and that the pending-approval queue + recent audit feed are
populated from real data.
"""

import asyncio

from app.db import session_scope
from app.models import AdminUser, Tenant
from app.models.admin import ROLE_OWNER
from app.models.tenant import TENANT_PENDING
from app.modules.auth.service import AuthService


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

async def _seed_owner_tenant() -> None:
    async with session_scope() as session:
        auth_service = AuthService(session)
        tenant = Tenant(name="Owner Tenant", slug="ownertenant", status="active")
        session.add(tenant)
        await session.flush()
        session.add(
            AdminUser(
                tenant_id=tenant.id,
                email="owner@x.test",
                full_name="Owner Admin",
                password_hash=auth_service.hash_password("owner-pw"),
                is_active=True,
                role=ROLE_OWNER,
            )
        )


async def _seed_pending_tenant(slug: str = "pendingco") -> None:
    async with session_scope() as session:
        session.add(Tenant(name="Pending Co", slug=slug, status=TENANT_PENDING))


def _login_as(client, email: str, password: str) -> dict[str, str]:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['token']}"}


# ---------------------------------------------------------------------------
# Auth + role gate
# ---------------------------------------------------------------------------

def test_overview_requires_authentication(client):
    resp = client.get("/api/v1/admin/overview")
    assert resp.status_code == 401


def test_owner_cannot_get_overview(client):
    asyncio.run(_seed_owner_tenant())
    headers = _login_as(client, "owner@x.test", "owner-pw")
    resp = client.get("/api/v1/admin/overview", headers=headers)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Shape + data
# ---------------------------------------------------------------------------

def test_platform_admin_overview_shape(client):
    headers = _login_as(client, "admin@example.com", "supersecurepassword")
    resp = client.get("/api/v1/admin/overview", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    for key in ("tenant_status", "totals", "committed_resources", "pending_tenants", "recent_events"):
        assert key in body, f"missing top-level key: {key}"

    for key in ("active", "pending", "suspended", "rejected", "total"):
        assert key in body["tenant_status"]
    for key in ("tenants", "admins", "apps", "databases", "plans"):
        assert key in body["totals"]
    for key in ("cpu_millicores", "mem_mb", "disk_mb"):
        assert key in body["committed_resources"]

    # The bootstrap platform-admin tenant is counted.
    assert body["tenant_status"]["total"] >= 1
    assert body["totals"]["admins"] >= 1
    assert isinstance(body["pending_tenants"], list)
    assert isinstance(body["recent_events"], list)


def test_overview_surfaces_pending_tenant(client):
    asyncio.run(_seed_pending_tenant("pendingco"))
    headers = _login_as(client, "admin@example.com", "supersecurepassword")
    resp = client.get("/api/v1/admin/overview", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["tenant_status"]["pending"] >= 1
    slugs = {t["slug"] for t in body["pending_tenants"]}
    assert "pendingco" in slugs


def test_overview_recent_events_reflect_approval(client):
    """Approving a pending tenant writes an audit event that the feed surfaces."""
    asyncio.run(_seed_pending_tenant("approveme"))
    headers = _login_as(client, "admin@example.com", "supersecurepassword")

    approve = client.post("/api/v1/tenants/approveme/approve", headers=headers)
    assert approve.status_code == 200, approve.text

    resp = client.get("/api/v1/admin/overview", headers=headers)
    assert resp.status_code == 200, resp.text
    events = resp.json()["recent_events"]
    assert any(
        e["action"] == "tenant.approve" and e["target"] == "approveme" for e in events
    ), events
