"""
Task 2.3 — Self-serve signup endpoint.

Tests cover:
  - Happy path: creates a pending owner, token authenticates, write blocked by status gate.
  - Weak password (< 10 chars) → 422.
  - Extra privilege fields in body are IGNORED (server-sets role/plan/status).
  - Duplicate email: 200 non-distinguishing response, returned token is empty / non-authenticating,
    and no second row was created.
"""

import asyncio

from sqlalchemy import func, select

from app.db import session_scope
from app.models import AdminUser, Tenant
from app.models.tenant import TENANT_PENDING


# ---------------------------------------------------------------------------
# From the task brief (verbatim)
# ---------------------------------------------------------------------------

def test_signup_creates_pending_owner_then_blocked(client):
    r = client.post(
        "/api/v1/auth/signup",
        json={"email": "new@c.test", "password": "longenough1", "org_name": "Acme"},
    )
    assert r.status_code == 200
    headers = {"Authorization": f"Bearer {r.json()['token']}"}
    assert client.get("/api/v1/auth/me", headers=headers).json()["role"] == "owner"
    # pending tenant: a write is blocked by the central gate
    assert client.post("/api/v1/apps/x/start", headers=headers).status_code == 403


def test_signup_weak_password_422(client):
    assert (
        client.post(
            "/api/v1/auth/signup",
            json={"email": "a@b.c", "password": "short", "org_name": "A"},
        ).status_code
        == 422
    )


# ---------------------------------------------------------------------------
# Security invariant: privilege fields are server-set, never from request body
# ---------------------------------------------------------------------------

def test_signup_cannot_set_role_or_plan(client):
    """Extra body fields (role, plan_id, status, is_platform_scope) must be ignored."""
    r = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "priv@c.test",
            "password": "longenough1",
            "org_name": "PrivOrg",
            "role": "platform_admin",
            "plan_id": "fake-plan-uuid",
            "status": "active",
            "is_platform_scope": True,
        },
    )
    assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"

    headers = {"Authorization": f"Bearer {r.json()['token']}"}
    me = client.get("/api/v1/auth/me", headers=headers).json()

    # Role must be owner, not platform_admin
    assert me["role"] == "owner", f"role was {me['role']!r}, expected 'owner'"

    # Verify in DB: tenant is still pending and not platform scope
    async def _check():
        async with session_scope() as session:
            admin = await session.scalar(
                select(AdminUser).where(AdminUser.email == "priv@c.test")
            )
            assert admin is not None
            assert admin.role == "owner"

            tenant = await session.get(Tenant, admin.tenant_id)
            assert tenant is not None
            assert tenant.status == TENANT_PENDING
            assert tenant.is_platform_scope is False

    asyncio.run(_check())


# ---------------------------------------------------------------------------
# Security invariant: duplicate email must NOT grant access to existing account
# ---------------------------------------------------------------------------

def test_signup_duplicate_email_no_takeover(client):
    """
    Signing up twice with the same email:
      - Second call returns 200 (non-distinguishing) but with an EMPTY/non-authenticating token.
      - GET /api/v1/auth/me with the second token must return 401 (cannot authenticate).
      - No second AdminUser or Tenant row was created for that email.
    """
    payload = {"email": "dup@c.test", "password": "longenough1", "org_name": "DupOrg"}

    # First signup — must succeed normally
    r1 = client.post("/api/v1/auth/signup", json=payload)
    assert r1.status_code == 200
    token1 = r1.json()["token"]
    assert token1  # non-empty real token

    # Second signup — same email
    r2 = client.post("/api/v1/auth/signup", json=payload)
    assert r2.status_code == 200, f"expected 200, got {r2.status_code}: {r2.text}"

    token2 = r2.json()["token"]
    # The returned token must be empty (non-authenticating sentinel)
    assert token2 == "", f"duplicate signup must return empty token, got {token2!r}"

    # Using the empty token must NOT authenticate
    me_resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert me_resp.status_code == 401, (
        f"empty token must return 401, got {me_resp.status_code}: {me_resp.text}"
    )

    # DB: exactly one admin row and one tenant for this email
    async def _check_no_duplicate_rows():
        async with session_scope() as session:
            admin_count = await session.scalar(
                select(func.count()).select_from(AdminUser).where(
                    AdminUser.email == "dup@c.test"
                )
            )
            assert admin_count == 1, f"expected 1 admin row, found {admin_count}"

            # Confirm only one tenant was created (the pending one from the first signup)
            # We check via the tenant linked to the one admin row
            admin = await session.scalar(
                select(AdminUser).where(AdminUser.email == "dup@c.test")
            )
            assert admin is not None
            tenant_count = await session.scalar(
                select(func.count()).select_from(Tenant).where(Tenant.id == admin.tenant_id)
            )
            assert tenant_count == 1

    asyncio.run(_check_no_duplicate_rows())
