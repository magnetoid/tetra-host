"""Cross-tenant isolation on engine deployments.

Deployment ids are global uuids, so every route that takes one must check the row's
tenant itself; knowing another tenant's id must not let you read, explain or roll it back.
The build-log stream is covered in ``test_deploys_stream.py``.
"""

import asyncio

from app.db import session_scope
from app.models import AdminUser, Deployment, Plan, Tenant, TenantResource
from app.models.deployment import STATUS_READY
from app.models.tenant_resource import PROVIDER_DOCKER, RESOURCE_TYPE_APP
from app.modules.auth.service import AuthService

PASSWORD = "isolation-pass"


async def _seed(slug: str, project: str) -> str:
    async with session_scope() as session:
        auth = AuthService(session)
        plan = Plan(key=f"plan_{slug}", name="P", max_apps=10)
        session.add(plan)
        await session.flush()
        tenant = Tenant(name=slug, slug=slug, status="active", plan_id=plan.id)
        session.add(tenant)
        await session.flush()
        session.add(AdminUser(
            tenant_id=tenant.id, email=f"owner@{slug}.test", full_name="Owner",
            password_hash=auth.hash_password(PASSWORD), is_active=True,
        ))
        session.add(TenantResource(
            tenant_id=tenant.id, provider=PROVIDER_DOCKER, resource_type=RESOURCE_TYPE_APP,
            external_id=project, display_name=project,
        ))
        deployment = Deployment(
            tenant_id=tenant.id, project=project, status=STATUS_READY,
            image=f"tetra/{project}:1", log="✓ live", domain=f"{project}.example.com",
        )
        session.add(deployment)
        await session.flush()
        return deployment.id


def _login(client, slug: str) -> dict[str, str]:
    resp = client.post("/api/v1/auth/login", json={"email": f"owner@{slug}.test", "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['token']}"}


def test_tenant_cannot_touch_another_tenants_deployment(client):
    victim = asyncio.run(_seed("victim", "secret"))
    own = asyncio.run(_seed("attacker", "mine"))
    headers = _login(client, "attacker")

    assert client.get(f"/api/v1/deploys/{own}", headers=headers).status_code == 200
    assert client.get(f"/api/v1/deploys/{victim}", headers=headers).status_code == 404
    assert client.get(f"/api/v1/deploys/{victim}/explain", headers=headers).status_code == 404
    rollback = client.post(f"/api/v1/deploys/{victim}/rollback", headers=headers)
    assert rollback.status_code in (403, 404), rollback.text


def test_tenant_cannot_read_another_tenants_app_observability(client):
    asyncio.run(_seed("victim", "secret"))
    asyncio.run(_seed("attacker", "mine"))
    headers = _login(client, "attacker")
    # The attacker's own app resolves (Umami/GlitchTip are unset in tests, so 200 not-ready).
    assert client.get("/api/v1/apps/mine/analytics", headers=headers).status_code == 200
    for path in ("analytics", "errors", "errors/1/explain"):
        assert client.get(f"/api/v1/apps/secret/{path}", headers=headers).status_code == 404, path
