"""Editorial-dashboard aggregates on GET /api/v1/dashboard (deploys/24h, monitors,
recent deployments) — all computed over existing tables."""

import asyncio
import os

from app.db import session_scope
from app.models.deployment import STATUS_ERROR, STATUS_READY, Deployment
from app.models.uptime import UPTIME_DOWN, UPTIME_UP, UptimeMonitor

ADMIN_EMAIL = os.environ.get("ADMIN_BOOTSTRAP_EMAIL", "admin@example.com")
ADMIN_PASS = os.environ.get("ADMIN_BOOTSTRAP_PASSWORD", "supersecurepassword")


def _headers(client) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


async def _tenant_id(email: str) -> str:
    from sqlalchemy import select

    from app.models import AdminUser

    async with session_scope() as s:
        admin = (await s.scalars(select(AdminUser).where(AdminUser.email == email))).first()
        return admin.tenant_id


async def _seed(tenant_id: str) -> None:
    async with session_scope() as s:
        s.add(Deployment(tenant_id=tenant_id, project="blog", ref="main", commit="abcdef1234", status=STATUS_READY, domain="blog.example.com"))
        s.add(Deployment(tenant_id=tenant_id, project="api", ref="main", commit="0099aa", status=STATUS_ERROR))
        s.add(UptimeMonitor(tenant_id=tenant_id, name="up", url="https://a", status=UPTIME_UP))
        s.add(UptimeMonitor(tenant_id=tenant_id, name="down", url="https://b", status=UPTIME_DOWN))


def test_dashboard_returns_editorial_aggregates(client):
    headers = _headers(client)  # ensures bootstrap admin exists
    tid = asyncio.run(_tenant_id(ADMIN_EMAIL))
    asyncio.run(_seed(tid))

    body = client.get("/api/v1/dashboard", headers=headers).json()
    m = body["metrics"]
    assert m["deploys_24h"] == 2
    assert m["deploys_ok_24h"] == 1
    assert m["monitors_total"] == 2
    assert m["monitors_up"] == 1

    deps = body["recent_deployments"]
    assert len(deps) == 2
    projects = {d["project"] for d in deps}
    assert projects == {"blog", "api"}
    # Commit is short-hashed to 7 chars.
    blog = next(d for d in deps if d["project"] == "blog")
    assert blog["commit"] == "abcdef1"
    assert blog["status"] == STATUS_READY
