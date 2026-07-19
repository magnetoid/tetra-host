"""Platform audit log — GET /api/v1/audit (platform-admin only, filtered + paged)."""

import asyncio

from app.db import session_scope
from app.models import AdminUser, Plan, Tenant
from app.models.admin import ROLE_OWNER, ROLE_PLATFORM_ADMIN
from app.models.audit import AuditEvent
from app.modules.auth.service import AuthService


async def _seed(*, slug: str, email: str, role: str) -> None:
    async with session_scope() as session:
        auth = AuthService(session)
        plan = Plan(key=f"plan_{slug}", name="P", max_apps=10)
        session.add(plan)
        await session.flush()
        tenant = Tenant(name=slug, slug=slug, status="active", plan_id=plan.id)
        session.add(tenant)
        await session.flush()
        session.add(
            AdminUser(
                tenant_id=tenant.id, email=email, full_name="A", role=role,
                password_hash=auth.hash_password("audit-pass"), is_active=True,
            )
        )


async def _seed_events() -> None:
    async with session_scope() as session:
        for i in range(3):
            session.add(AuditEvent(actor_email="root@x.test", action="tenant.approve", target=f"t{i}"))
        session.add(AuditEvent(actor_email="other@x.test", action="tenant.reject", target="t9"))


def _login(client, email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "audit-pass"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_audit_requires_platform_admin(client):
    assert client.get("/api/v1/audit").status_code == 401
    asyncio.run(_seed(slug="ao", email="o@ao.test", role=ROLE_OWNER))
    headers = _login(client, "o@ao.test")
    assert client.get("/api/v1/audit", headers=headers).status_code == 403


def test_audit_lists_filters_and_pages(client):
    asyncio.run(_seed(slug="ap", email="p@ap.test", role=ROLE_PLATFORM_ADMIN))
    asyncio.run(_seed_events())
    headers = _login(client, "p@ap.test")

    # Full list — newest first, total reflects all 4 events.
    body = client.get("/api/v1/audit", headers=headers).json()
    assert body["total"] == 4
    assert len(body["events"]) == 4
    assert {e["action"] for e in body["events"]} == {"tenant.approve", "tenant.reject"}

    # Filter by action substring.
    approved = client.get("/api/v1/audit?action=approve", headers=headers).json()
    assert approved["total"] == 3
    assert all(e["action"] == "tenant.approve" for e in approved["events"])

    # Filter by actor.
    other = client.get("/api/v1/audit?actor=other", headers=headers).json()
    assert other["total"] == 1
    assert other["events"][0]["actor_email"] == "other@x.test"


def test_audit_csv_export_requires_platform_admin(client):
    assert client.get("/api/v1/audit/export.csv").status_code == 401
    asyncio.run(_seed(slug="co", email="o@co.test", role=ROLE_OWNER))
    headers = _login(client, "o@co.test")
    assert client.get("/api/v1/audit/export.csv", headers=headers).status_code == 403


def test_audit_csv_export_returns_downloadable_csv(client):
    asyncio.run(_seed(slug="cp", email="p@cp.test", role=ROLE_PLATFORM_ADMIN))
    asyncio.run(_seed_events())
    headers = _login(client, "p@cp.test")

    resp = client.get("/api/v1/audit/export.csv", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in resp.headers.get("content-disposition", "")
    lines = resp.text.strip().splitlines()
    assert lines[0] == "created_at,actor_email,action,target,details"
    assert len(lines) == 1 + 4  # header + 4 events
    assert any("tenant.reject" in line for line in lines)

    # Filter carries through to the export.
    filtered = client.get("/api/v1/audit/export.csv?action=approve", headers=headers)
    assert len(filtered.text.strip().splitlines()) == 1 + 3

    # Pagination clamps + reports limit/offset.
    page = client.get("/api/v1/audit?limit=2&offset=2", headers=headers).json()
    assert page["limit"] == 2 and page["offset"] == 2
    assert len(page["events"]) == 2
