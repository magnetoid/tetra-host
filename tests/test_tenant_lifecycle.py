"""
Task 2.4 — Tenant approval lifecycle endpoints + audit.

Covers:
  - Signup → pending; platform admin approves → 200, status == "active".
  - After approval, owner's write is NO LONGER blocked by the status gate (may fail
    for other provider reasons, but NOT 403 "Tenant is not active.").
  - Owner calling approve → 403 (platform-admin gate).
  - Invalid transition: approving an already-active tenant → 409.
  - AuditEvent row written on approve.
  - reject, suspend, reactivate basic transitions.
"""

import asyncio

from sqlalchemy import select

from app.db import session_scope
from app.models.audit import AuditEvent
from app.models.tenant import TENANT_ACTIVE, TENANT_PENDING, TENANT_REJECTED, TENANT_SUSPENDED

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "supersecurepassword"


def _platform_admin_token(client) -> str:
    r = client.post(
        "/api/v1/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert r.status_code == 200, f"platform admin login failed: {r.text}"
    return r.json()["token"]


def _signup_and_get_token(client, email: str, org: str) -> tuple[str, str]:
    """Sign up, return (token, slug)."""
    r = client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "longenough1", "org_name": org},
    )
    assert r.status_code == 200, f"signup failed: {r.text}"
    token = r.json()["token"]

    # Derive the tenant slug from the org name (same slugify as server)
    import re
    slug = re.sub(r"[^a-z0-9-]", "-", org.lower()).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return token, slug


# ---------------------------------------------------------------------------
# Core lifecycle tests
# ---------------------------------------------------------------------------


def test_approve_tenant_happy_path(client):
    """Platform admin approves a pending tenant → 200, status == 'active'."""
    owner_token, slug = _signup_and_get_token(client, "owner@lc.test", "LifecycleCo")
    admin_token = _platform_admin_token(client)

    r = client.post(
        f"/api/v1/tenants/{slug}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, f"approve failed: {r.text}"
    body = r.json()
    assert body["status"] == TENANT_ACTIVE
    assert body["slug"] == slug


def test_approve_unlocks_owner_write(client):
    """After approval the owner's write is no longer blocked by the 403 status gate."""
    owner_token, slug = _signup_and_get_token(client, "owner2@lc.test", "LifecycleCo2")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    admin_token = _platform_admin_token(client)

    # Confirm blocked before approve
    r = client.post("/api/v1/apps/x/start", headers=owner_headers)
    assert r.status_code == 403, "expected 403 before approval"
    assert "not active" in r.json()["detail"].lower()

    # Approve
    client.post(
        f"/api/v1/tenants/{slug}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # Now the status gate must NOT return 403 "Tenant is not active."
    r2 = client.post("/api/v1/apps/x/start", headers=owner_headers)
    if r2.status_code == 403:
        assert "not active" not in r2.json().get("detail", "").lower(), (
            f"Status gate still blocking: {r2.text}"
        )


def test_owner_cannot_approve(client):
    """An owner (non-platform-admin) calling /approve → 403."""
    owner_token, slug = _signup_and_get_token(client, "owner3@lc.test", "LifecycleCo3")
    r = client.post(
        f"/api/v1/tenants/{slug}/approve",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text}"


def test_approve_invalid_transition_409(client):
    """Approving an already-active tenant → 409."""
    owner_token, slug = _signup_and_get_token(client, "owner4@lc.test", "LifecycleCo4")
    admin_token = _platform_admin_token(client)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # First approve (valid)
    r = client.post(f"/api/v1/tenants/{slug}/approve", headers=admin_headers)
    assert r.status_code == 200

    # Second approve → 409 (already active)
    r2 = client.post(f"/api/v1/tenants/{slug}/approve", headers=admin_headers)
    assert r2.status_code == 409, f"expected 409, got {r2.status_code}: {r2.text}"


def test_approve_writes_audit_event(client):
    """An AuditEvent row is persisted when a tenant is approved."""
    owner_token, slug = _signup_and_get_token(client, "owner5@lc.test", "LifecycleCo5")
    admin_token = _platform_admin_token(client)

    r = client.post(
        f"/api/v1/tenants/{slug}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200

    async def _check():
        async with session_scope() as session:
            event = await session.scalar(
                select(AuditEvent).where(
                    AuditEvent.action == "tenant.approve",
                    AuditEvent.target == slug,
                )
            )
            assert event is not None, "AuditEvent row missing after approve"
            assert event.actor_email == ADMIN_EMAIL

    asyncio.run(_check())


# ---------------------------------------------------------------------------
# Other lifecycle transitions
# ---------------------------------------------------------------------------


def test_reject_pending_tenant(client):
    """Platform admin rejects a pending tenant → status == 'rejected'."""
    _, slug = _signup_and_get_token(client, "owner6@lc.test", "LifecycleCo6")
    admin_headers = {"Authorization": f"Bearer {_platform_admin_token(client)}"}

    r = client.post(f"/api/v1/tenants/{slug}/reject", headers=admin_headers)
    assert r.status_code == 200, f"reject failed: {r.text}"
    assert r.json()["status"] == TENANT_REJECTED


def test_reject_invalid_transition_409(client):
    """Rejecting an active tenant → 409."""
    _, slug = _signup_and_get_token(client, "owner7@lc.test", "LifecycleCo7")
    admin_headers = {"Authorization": f"Bearer {_platform_admin_token(client)}"}

    # First approve to make it active
    client.post(f"/api/v1/tenants/{slug}/approve", headers=admin_headers)

    r = client.post(f"/api/v1/tenants/{slug}/reject", headers=admin_headers)
    assert r.status_code == 409, f"expected 409, got {r.status_code}: {r.text}"


def test_suspend_active_tenant(client):
    """Platform admin suspends an active tenant → status == 'suspended'."""
    _, slug = _signup_and_get_token(client, "owner8@lc.test", "LifecycleCo8")
    admin_headers = {"Authorization": f"Bearer {_platform_admin_token(client)}"}

    client.post(f"/api/v1/tenants/{slug}/approve", headers=admin_headers)

    r = client.post(f"/api/v1/tenants/{slug}/suspend", headers=admin_headers)
    assert r.status_code == 200, f"suspend failed: {r.text}"
    assert r.json()["status"] == TENANT_SUSPENDED


def test_suspend_invalid_transition_409(client):
    """Suspending a pending tenant → 409."""
    _, slug = _signup_and_get_token(client, "owner9@lc.test", "LifecycleCo9")
    admin_headers = {"Authorization": f"Bearer {_platform_admin_token(client)}"}

    r = client.post(f"/api/v1/tenants/{slug}/suspend", headers=admin_headers)
    assert r.status_code == 409, f"expected 409, got {r.status_code}: {r.text}"


def test_reactivate_suspended_tenant(client):
    """Platform admin reactivates a suspended tenant → status == 'active'."""
    _, slug = _signup_and_get_token(client, "owner10@lc.test", "LifecycleCo10")
    admin_headers = {"Authorization": f"Bearer {_platform_admin_token(client)}"}

    client.post(f"/api/v1/tenants/{slug}/approve", headers=admin_headers)
    client.post(f"/api/v1/tenants/{slug}/suspend", headers=admin_headers)

    r = client.post(f"/api/v1/tenants/{slug}/reactivate", headers=admin_headers)
    assert r.status_code == 200, f"reactivate failed: {r.text}"
    assert r.json()["status"] == TENANT_ACTIVE


def test_reactivate_invalid_transition_409(client):
    """Reactivating a pending tenant → 409."""
    _, slug = _signup_and_get_token(client, "owner11@lc.test", "LifecycleCo11")
    admin_headers = {"Authorization": f"Bearer {_platform_admin_token(client)}"}

    r = client.post(f"/api/v1/tenants/{slug}/reactivate", headers=admin_headers)
    assert r.status_code == 409, f"expected 409, got {r.status_code}: {r.text}"


def test_approve_unknown_tenant_404(client):
    """Approving a non-existent tenant slug → 404."""
    admin_headers = {"Authorization": f"Bearer {_platform_admin_token(client)}"}
    r = client.post("/api/v1/tenants/no-such-slug/approve", headers=admin_headers)
    assert r.status_code == 404, f"expected 404, got {r.status_code}: {r.text}"


def test_tenant_summary_has_status_and_plan_key(client):
    """GET /tenants returns TenantSummary with status and plan_key fields."""
    _, slug = _signup_and_get_token(client, "owner12@lc.test", "LifecycleCo12")
    admin_headers = {"Authorization": f"Bearer {_platform_admin_token(client)}"}

    r = client.get("/api/v1/tenants", headers=admin_headers)
    assert r.status_code == 200
    # Find our newly-created tenant
    summaries = {t["slug"]: t for t in r.json()}
    assert slug in summaries, f"{slug} not in {list(summaries)}"
    t = summaries[slug]
    assert "status" in t, "TenantSummary missing 'status'"
    assert t["status"] == TENANT_PENDING
    assert "plan_key" in t, "TenantSummary missing 'plan_key'"
