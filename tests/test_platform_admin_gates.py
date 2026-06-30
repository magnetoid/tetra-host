"""Task 1.5 — require_platform_admin gates.

Seed a tenant + admin with role="owner", log in via /api/v1/auth/login, and
assert HTTP 403 on every endpoint that should be platform-admin-only.
Also asserts that the bootstrap platform_admin is NOT 403 on those same endpoints.
"""

import asyncio

from app.db import session_scope
from app.models import AdminUser, Tenant
from app.models.admin import ROLE_OWNER, ROLE_PLATFORM_ADMIN
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


def _login_as(client, email: str, password: str) -> dict[str, str]:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['token']}"}


# ---------------------------------------------------------------------------
# Tests — owner must get 403
# ---------------------------------------------------------------------------

def test_owner_cannot_list_tenants(client):
    asyncio.run(_seed_owner_tenant())
    headers = _login_as(client, "owner@x.test", "owner-pw")
    resp = client.get("/api/v1/tenants", headers=headers)
    assert resp.status_code == 403


def test_owner_cannot_create_tenant(client):
    asyncio.run(_seed_owner_tenant())
    headers = _login_as(client, "owner@x.test", "owner-pw")
    resp = client.post("/api/v1/tenants", headers=headers, json={"name": "Hack", "slug": "hack"})
    assert resp.status_code == 403


def test_owner_cannot_activate_tenant(client):
    asyncio.run(_seed_owner_tenant())
    headers = _login_as(client, "owner@x.test", "owner-pw")
    resp = client.post("/api/v1/tenants/ownertenant/activate", headers=headers)
    assert resp.status_code == 403


def test_owner_cannot_deactivate_tenant(client):
    asyncio.run(_seed_owner_tenant())
    headers = _login_as(client, "owner@x.test", "owner-pw")
    resp = client.post("/api/v1/tenants/ownertenant/deactivate", headers=headers)
    assert resp.status_code == 403


def test_owner_cannot_create_tenant_admin(client):
    asyncio.run(_seed_owner_tenant())
    headers = _login_as(client, "owner@x.test", "owner-pw")
    resp = client.post(
        "/api/v1/tenant-admins",
        headers=headers,
        json={
            "tenant_slug": "ownertenant",
            "email": "new@x.test",
            "full_name": "New",
            "password": "pw",
        },
    )
    assert resp.status_code == 403


def test_owner_cannot_create_tenant_resource(client):
    asyncio.run(_seed_owner_tenant())
    headers = _login_as(client, "owner@x.test", "owner-pw")
    resp = client.post(
        "/api/v1/tenant-resources",
        headers=headers,
        json={
            "tenant_slug": "ownertenant",
            "provider": "coolify",
            "resource_type": "site",
            "external_id": "site-123",
            "display_name": "Test Site",
        },
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Tests — platform_admin must NOT get 403 on GET /tenants
# ---------------------------------------------------------------------------

def test_platform_admin_can_list_tenants(client):
    """Bootstrap admin (platform_admin) must be allowed through."""
    headers = _login_as(client, "admin@example.com", "supersecurepassword")
    resp = client.get("/api/v1/tenants", headers=headers)
    # 200 (no tenants yet) — just not 403
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tests — AdminSummary.role field is present
# ---------------------------------------------------------------------------

def test_login_response_includes_role(client):
    """AuthResponse.admin should expose the role field."""
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "supersecurepassword"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "role" in body["admin"]
    assert body["admin"]["role"] == ROLE_PLATFORM_ADMIN


def test_me_includes_role_for_owner(client):
    """GET /auth/me should expose the role field for an owner too."""
    asyncio.run(_seed_owner_tenant())
    headers = _login_as(client, "owner@x.test", "owner-pw")
    resp = client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["role"] == ROLE_OWNER


# ---------------------------------------------------------------------------
# Tests — GET /api/v1/admin must be platform-admin-only (Task 1.5 fix)
# ---------------------------------------------------------------------------

def test_owner_cannot_get_admin_summary(client):
    """Owner tenant admin must get 403 on GET /api/v1/admin."""
    asyncio.run(_seed_owner_tenant())
    headers = _login_as(client, "owner@x.test", "owner-pw")
    resp = client.get("/api/v1/admin", headers=headers)
    assert resp.status_code == 403


def test_platform_admin_can_get_admin_summary(client):
    """Bootstrap platform_admin must be allowed through GET /api/v1/admin."""
    headers = _login_as(client, "admin@example.com", "supersecurepassword")
    resp = client.get("/api/v1/admin", headers=headers)
    assert resp.status_code == 200
