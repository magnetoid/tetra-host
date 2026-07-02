"""Instant rollback: redeploy a prior deployment's image without rebuilding."""

import asyncio

from app.config import get_settings
from app.db import session_scope
from app.models import AdminUser, Plan, Tenant, TenantResource
from app.models.deployment import STATUS_ERROR, STATUS_READY, Deployment
from app.models.tenant_resource import PROVIDER_DOCKER, RESOURCE_TYPE_APP
from app.modules.auth.service import AuthService
from app.modules.deploys.service import DeploysService


async def _seed_deploy(
    *, slug: str, email: str, project: str = "blog",
    image: str = "tetra-blog:abc123", status: str = STATUS_READY, with_app: bool = True,
) -> str:
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
                tenant_id=tenant.id, email=email, full_name="Owner",
                password_hash=auth.hash_password("rb-pass"), is_active=True,
            )
        )
        if with_app:
            session.add(
                TenantResource(
                    tenant_id=tenant.id, provider=PROVIDER_DOCKER,
                    resource_type=RESOURCE_TYPE_APP, external_id=project, display_name=project,
                )
            )
        dep = Deployment(tenant_id=tenant.id, project=project, status=status, image=image, port=3000)
        session.add(dep)
        await session.flush()
        return dep.id


def _login(client, email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "rb-pass"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _enable_actions(monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_provider_actions", True)


def _noop_rollback(monkeypatch):
    async def _noop(self, *a, **k):
        return None

    monkeypatch.setattr(DeploysService, "_run_rollback", _noop)


def test_rollback_creates_new_deployment_pinned_to_old_image(client, monkeypatch):
    _enable_actions(monkeypatch)
    _noop_rollback(monkeypatch)
    dep_id = asyncio.run(_seed_deploy(slug="rb", email="owner@rb.test", image="tetra-blog:abc123"))
    headers = _login(client, "owner@rb.test")
    r = client.post(f"/api/v1/deploys/{dep_id}/rollback", headers=headers)
    assert r.status_code == 200
    new_id = r.json()["deployment_id"]
    assert new_id and new_id != dep_id
    status = client.get(f"/api/v1/deploys/{new_id}", headers=headers).json()
    assert status["image"] == "tetra-blog:abc123"
    assert status["project"] == "blog"


def test_rollback_rejects_non_ready_deployment(client, monkeypatch):
    _enable_actions(monkeypatch)
    _noop_rollback(monkeypatch)
    dep_id = asyncio.run(
        _seed_deploy(slug="rbe", email="owner@rbe.test", status=STATUS_ERROR, image="")
    )
    headers = _login(client, "owner@rbe.test")
    assert client.post(f"/api/v1/deploys/{dep_id}/rollback", headers=headers).status_code == 409


def test_rollback_denies_foreign_deployment(client, monkeypatch):
    _enable_actions(monkeypatch)
    _noop_rollback(monkeypatch)
    foreign = asyncio.run(_seed_deploy(slug="rba", email="a@rba.test"))
    asyncio.run(_seed_deploy(slug="rbb", email="b@rbb.test", project="other"))
    headers_b = _login(client, "b@rbb.test")
    assert client.post(f"/api/v1/deploys/{foreign}/rollback", headers=headers_b).status_code == 404


def test_rollback_requires_existing_app(client, monkeypatch):
    _enable_actions(monkeypatch)
    _noop_rollback(monkeypatch)
    dep_id = asyncio.run(
        _seed_deploy(slug="rbn", email="owner@rbn.test", with_app=False)
    )
    headers = _login(client, "owner@rbn.test")
    assert client.post(f"/api/v1/deploys/{dep_id}/rollback", headers=headers).status_code == 404
