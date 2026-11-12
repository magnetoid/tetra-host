"""Cancelling a deploy: allowed while it clones and builds, refused once the new version starts."""

import asyncio

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.db import session_scope
from app.models import AdminUser, Plan, Tenant, TenantResource
from app.models.deployment import (
    STATUS_BUILDING,
    STATUS_CANCELLED,
    STATUS_ERROR,
    STATUS_READY,
    Deployment,
)
from app.models.tenant_resource import PROVIDER_DOCKER, RESOURCE_TYPE_APP
from app.modules.auth.service import AuthService
from app.modules.deploys.service import DeploysService
from app.services.builder import BuildError, BuildResult
from app.services.docker_engine import DockerEngineError

GIT = "https://github.com/example/blog.git"


async def _seed(*, slug: str = "cx", with_app: bool = False) -> str:
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
                tenant_id=tenant.id, email=f"o@{slug}.test", full_name="Owner",
                password_hash=auth.hash_password("cx-pass"), is_active=True,
            )
        )
        if with_app:
            session.add(
                TenantResource(
                    tenant_id=tenant.id, provider=PROVIDER_DOCKER,
                    resource_type=RESOURCE_TYPE_APP, external_id="blog", display_name="blog",
                )
            )
        return tenant.id


async def _app_recorded(tenant_id: str) -> bool:
    async with session_scope() as session:
        row = await session.scalar(
            select(TenantResource).where(
                TenantResource.tenant_id == tenant_id, TenantResource.external_id == "blog"
            )
        )
        return row is not None


async def _deployment(deployment_id: str) -> Deployment:
    async with session_scope() as session:
        deployment = await session.get(Deployment, deployment_id)
        assert deployment is not None
        return deployment


async def _wait_for(predicate, timeout: float = 5.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not await predicate():
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("condition not reached in time")
        await asyncio.sleep(0.01)


@pytest.fixture
def engine_fakes(monkeypatch):
    """A build that waits on ``build_gate``, and a stack start that records calls."""
    monkeypatch.setattr(get_settings(), "enable_provider_actions", True)
    state = {"build_gate": None, "deploy_gate": None, "building": False, "deployed": []}

    async def fake_build(self, git_url, ref, *, project, on_line=None):
        state["building"] = True
        if on_line is not None:
            await on_line("step 1/3 : FROM node")
        await state["build_gate"].wait()
        return BuildResult(image=f"tetra-{project}:abc", builder="dockerfile", port=3000)

    async def fake_deploy(self, project, compose_yaml, env=None):
        if state["deploy_gate"] is not None:
            await state["deploy_gate"].wait()
        state["deployed"].append(project)
        return {"ok": True, "project": project}

    async def noop(self, *args, **kwargs):
        return None

    monkeypatch.setattr("app.services.builder.Builder.build_from_git", fake_build)
    monkeypatch.setattr("app.services.docker_engine.DockerEngine.deploy_stack", fake_deploy)
    monkeypatch.setattr(DeploysService, "_prune_old_images", noop)
    return state


def test_cancel_first_deploy_during_build_releases_the_reservation(client, engine_fakes):
    async def go():
        engine_fakes["build_gate"] = asyncio.Event()
        tenant_id = await _seed()
        service = DeploysService(None)
        dep_id = await service.start_deploy_for_tenant(
            tenant_id, git_url=GIT, ref="main", name="blog", port=3000
        )
        assert await _app_recorded(tenant_id)  # the reservation is the app record
        await _wait_for(lambda: _is(dep_id, STATUS_BUILDING))

        status = await service.cancel_for_tenant(tenant_id, dep_id)

        assert status == STATUS_CANCELLED
        deployment = await _deployment(dep_id)
        assert deployment.error == "Cancelled by user."
        assert "cancelled" in deployment.log
        assert engine_fakes["deployed"] == []
        assert not await _app_recorded(tenant_id)

    asyncio.run(go())


def test_cancel_redeploy_keeps_the_running_app(client, engine_fakes):
    async def go():
        engine_fakes["build_gate"] = asyncio.Event()
        tenant_id = await _seed(with_app=True)
        service = DeploysService(None)
        dep_id = await service.redeploy_for_tenant(
            tenant_id, git_url=GIT, ref="main", project="blog", port=3000
        )
        await _wait_for(lambda: _is(dep_id, STATUS_BUILDING))

        assert await service.cancel_for_tenant(tenant_id, dep_id) == STATUS_CANCELLED
        assert await _app_recorded(tenant_id)

    asyncio.run(go())


def test_failed_redeploy_keeps_the_running_app(client, monkeypatch, engine_fakes):
    async def failing_build(self, git_url, ref, *, project, on_line=None):
        raise BuildError(message="npm ERR! missing script: build", code=502)

    monkeypatch.setattr("app.services.builder.Builder.build_from_git", failing_build)

    async def go():
        tenant_id = await _seed(with_app=True)
        service = DeploysService(None)
        dep_id = await service.redeploy_for_tenant(
            tenant_id, git_url=GIT, ref="main", project="blog", port=3000
        )
        await _wait_for(lambda: _is(dep_id, STATUS_ERROR))
        assert await _app_recorded(tenant_id)

    asyncio.run(go())


def test_cancel_is_refused_once_the_new_version_is_starting(client, engine_fakes):
    async def go():
        engine_fakes["build_gate"] = asyncio.Event()
        engine_fakes["build_gate"].set()
        engine_fakes["deploy_gate"] = asyncio.Event()
        tenant_id = await _seed(with_app=True)
        service = DeploysService(None)
        dep_id = await service.redeploy_for_tenant(
            tenant_id, git_url=GIT, ref="main", project="blog", port=3000
        )
        await _wait_for(lambda: _log_has(dep_id, "starting container"))

        with pytest.raises(DockerEngineError) as exc:
            await service.cancel_for_tenant(tenant_id, dep_id)
        assert exc.value.code == 409

        engine_fakes["deploy_gate"].set()
        await _wait_for(lambda: _is(dep_id, STATUS_READY))
        assert engine_fakes["deployed"] == ["blog"]

    asyncio.run(go())


def test_cancel_marks_an_orphaned_deploy_cancelled(client, engine_fakes):
    """A deploy left 'building' by a panel restart has no task; cancel just closes it."""

    async def go():
        tenant_id = await _seed(with_app=True)
        async with session_scope() as session:
            deployment = Deployment(
                tenant_id=tenant_id, project="blog", status=STATUS_BUILDING, log="→ cloning"
            )
            session.add(deployment)
            await session.flush()
            dep_id = deployment.id

        status = await DeploysService(None).cancel_for_tenant(tenant_id, dep_id)

        assert status == STATUS_CANCELLED
        deployment = await _deployment(dep_id)
        assert deployment.status == STATUS_CANCELLED
        assert deployment.log.startswith("→ cloning\n✗ cancelled")
        assert await _app_recorded(tenant_id)

    asyncio.run(go())


def test_cancel_rejects_finished_and_foreign_deploys(client, engine_fakes):
    async def go():
        tenant_id = await _seed(with_app=True)
        other_id = await _seed(slug="other")
        async with session_scope() as session:
            done = Deployment(tenant_id=tenant_id, project="blog", status=STATUS_READY)
            running = Deployment(tenant_id=tenant_id, project="blog", status=STATUS_BUILDING)
            session.add_all([done, running])
            await session.flush()
            done_id, running_id = done.id, running.id

        service = DeploysService(None)
        with pytest.raises(DockerEngineError) as finished:
            await service.cancel_for_tenant(tenant_id, done_id)
        assert finished.value.code == 409
        with pytest.raises(DockerEngineError) as foreign:
            await service.cancel_for_tenant(other_id, running_id)
        assert foreign.value.code == 404
        assert (await _deployment(running_id)).status == STATUS_BUILDING

    asyncio.run(go())


def test_cancel_route_returns_status_and_404(client, engine_fakes):
    tenant_id = asyncio.run(_seed(with_app=True))

    async def orphan() -> str:
        async with session_scope() as session:
            deployment = Deployment(tenant_id=tenant_id, project="blog", status=STATUS_BUILDING)
            session.add(deployment)
            await session.flush()
            return deployment.id

    dep_id = asyncio.run(orphan())
    token = client.post(
        "/api/v1/auth/login", json={"email": "o@cx.test", "password": "cx-pass"}
    ).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(f"/api/v1/deploys/{dep_id}/cancel", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json() == {"ok": True, "deployment_id": dep_id, "status": "cancelled"}

    again = client.post(f"/api/v1/deploys/{dep_id}/cancel", headers=headers)
    assert again.status_code == 409
    missing = client.post("/api/v1/deploys/nope/cancel", headers=headers)
    assert missing.status_code == 404


async def _is(deployment_id: str, status: str) -> bool:
    return (await _deployment(deployment_id)).status == status


async def _log_has(deployment_id: str, text: str) -> bool:
    return text in ((await _deployment(deployment_id)).log or "")
