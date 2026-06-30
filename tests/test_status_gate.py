"""
Task 2.2 — Central tenant-status gate.

Tests that a suspended (or any non-active) tenant owner:
  - can still log in (login is a safe operation)
  - is blocked (403) on state-changing POST/PUT/PATCH/DELETE
  - is NOT blocked on safe GET requests

Platform admins and active-tenant owners are NOT blocked.

Also covers the HTML panel gate: a suspended tenant owner doing a panel POST
gets a REDIRECT (303), NOT a raw 403 JSON response.
"""

import asyncio
import re

from app.db import session_scope
from app.models import AdminUser, Tenant
from app.models.tenant import TENANT_ACTIVE, TENANT_SUSPENDED
from app.modules.auth.service import AuthService


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

async def _seed_suspended_owner() -> None:
    async with session_scope() as session:
        auth_service = AuthService(session)
        tenant = Tenant(name="Suspended Corp", slug="suspended-corp", status=TENANT_SUSPENDED)
        session.add(tenant)
        await session.flush()
        session.add(
            AdminUser(
                tenant_id=tenant.id,
                email="owner@suspended.test",
                full_name="Suspended Owner",
                password_hash=auth_service.hash_password("susp-password"),
                is_active=True,
            )
        )


async def _seed_active_owner() -> None:
    async with session_scope() as session:
        auth_service = AuthService(session)
        tenant = Tenant(name="Active Corp", slug="active-corp", status=TENANT_ACTIVE)
        session.add(tenant)
        await session.flush()
        session.add(
            AdminUser(
                tenant_id=tenant.id,
                email="owner@active.test",
                full_name="Active Owner",
                password_hash=auth_service.hash_password("active-password"),
                is_active=True,
            )
        )


def _login_suspended(client) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@suspended.test", "password": "susp-password"},
    )
    assert response.status_code == 200, f"login failed: {response.text}"
    return {"Authorization": f"Bearer {response.json()['token']}"}


def _login_active(client) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@active.test", "password": "active-password"},
    )
    assert response.status_code == 200, f"login failed: {response.text}"
    return {"Authorization": f"Bearer {response.json()['token']}"}


# ---------------------------------------------------------------------------
# Tests — suspended tenant
# ---------------------------------------------------------------------------

def test_suspended_owner_login_succeeds(client):
    """Login (POST /api/v1/auth/login) must still work for suspended tenants."""
    asyncio.run(_seed_suspended_owner())
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@suspended.test", "password": "susp-password"},
    )
    assert response.status_code == 200
    assert "token" in response.json()


def test_suspended_owner_post_blocked(client):
    """A suspended owner hitting any unsafe endpoint must get 403 with the status-gate detail."""
    asyncio.run(_seed_suspended_owner())
    headers = _login_suspended(client)
    # POST /api/v1/apps/anything/start — this route has NO explicit status dep,
    # proving the CENTRAL gate fires.
    response = client.post("/api/v1/apps/anything/start", headers=headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "Tenant is not active."


def test_suspended_owner_get_not_blocked_by_status_gate(client):
    """Safe GET requests must pass the status gate (may succeed or fail for other reasons)."""
    asyncio.run(_seed_suspended_owner())
    headers = _login_suspended(client)
    response = client.get("/api/v1/apps", headers=headers)
    # The gate must NOT return 403 with "Tenant is not active." on a GET.
    assert not (
        response.status_code == 403
        and response.json().get("detail") == "Tenant is not active."
    ), "Status gate must not block safe GET requests for suspended tenant"


# ---------------------------------------------------------------------------
# Tests — active tenant (no gate interference)
# ---------------------------------------------------------------------------

def test_active_owner_post_not_blocked_by_status_gate(client, monkeypatch):
    """An active-tenant owner's POST must not be blocked by the status gate."""
    asyncio.run(_seed_active_owner())
    headers = _login_active(client)
    # POST to a non-existent app — may 403 for tenant-scoping reasons, but NOT
    # because the status gate fired.
    response = client.post("/api/v1/apps/nonexistent-app/start", headers=headers)
    assert not (
        response.status_code == 403
        and response.json().get("detail") == "Tenant is not active."
    ), "Status gate must not block active-tenant owner"


# ---------------------------------------------------------------------------
# HTML panel status-gate: suspended tenant → REDIRECT, not raw 403 JSON
# ---------------------------------------------------------------------------

def _panel_login_suspended(client) -> None:
    """Log in the suspended owner via the HTML panel session (cookie auth)."""
    login_page = client.get("/auth/login")
    match = re.search(r'name="csrf_token" value="([^"]+)"', login_page.text)
    assert match is not None, "CSRF token not found on login page"
    csrf_token = match.group(1)
    resp = client.post(
        "/auth/login",
        data={
            "email": "owner@suspended.test",
            "password": "susp-password",
            "csrf_token": csrf_token,
            "next_url": "/dashboard",
        },
        follow_redirects=False,
    )
    # Login redirects (303) even for suspended tenant — that is correct
    assert resp.status_code in (200, 303), f"Panel login unexpected status: {resp.status_code}"


def test_suspended_tenant_panel_post_redirects_not_403(client):
    """A suspended tenant owner doing an HTML panel POST must get a REDIRECT (303),
    not a raw 403 JSON response. This verifies Item B: the panel status-gate
    mirrors how unauthenticated panel requests redirect instead of returning JSON.
    """
    asyncio.run(_seed_suspended_owner())
    _panel_login_suspended(client)

    # Fetch the maintenance page to get a CSRF token from the panel session
    page = client.get("/maintenance")
    # If a redirect to login occurred, login first via session and retry
    if page.status_code in (303, 302):
        # Follow the redirect chain manually
        page = client.get("/maintenance", follow_redirects=True)
    match = re.search(r'name="csrf_token" value="([^"]+)"', page.text)
    assert match is not None, f"No CSRF token found on maintenance page (status {page.status_code})"
    csrf_token = match.group(1)

    # POST to the maintenance /run route — a CSRF-protected panel POST
    resp = client.post(
        "/maintenance/run",
        data={"command": "cleanup:database", "csrf_token": csrf_token},
        follow_redirects=False,
    )

    # Must NOT be a raw 403 JSON — must be a redirect (302/303)
    assert resp.status_code in (302, 303), (
        f"Suspended tenant panel POST must redirect (302/303), got {resp.status_code}: {resp.text[:300]}"
    )
    # Must redirect somewhere meaningful (dashboard or login), not to a JSON error
    location = resp.headers.get("location", "")
    assert location, "Redirect must have a Location header"


def test_api_status_gate_still_returns_403_json(client):
    """The API path (Bearer token) must still return JSON 403 — unchanged by Item B."""
    asyncio.run(_seed_suspended_owner())
    headers = _login_suspended(client)
    response = client.post("/api/v1/apps/anything/start", headers=headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "Tenant is not active."
