import asyncio
import base64

from app.config import get_settings
from app.db import session_scope
from app.models import AdminUser, Plan, Tenant, TenantResource
from app.models.tenant_resource import PROVIDER_DOCKER, RESOURCE_TYPE_APP
from app.modules.auth.service import AuthService
from app.services.app_catalog import AppTemplate


async def _seed_apps_tenant() -> None:
    async with session_scope() as session:
        auth_service = AuthService(session)
        # Seed a plan with max_apps=10 so existing apps tests are not quota-blocked.
        plan = Plan(
            key="apps_test_plan",
            name="Apps Test Plan",
            max_apps=10,
            max_domains=0,
            cpu_millicores=500,
            mem_mb=512,
            disk_mb=2048,
        )
        session.add(plan)
        await session.flush()

        tenant = Tenant(name="Apps Tenant", slug="appst", status="active", plan_id=plan.id)
        session.add(tenant)
        await session.flush()
        session.add(
            AdminUser(
                tenant_id=tenant.id,
                email="owner@apps.test",
                full_name="Apps Owner",
                password_hash=auth_service.hash_password("apps-password"),
                is_active=True,
            )
        )
        session.add(
            TenantResource(
                tenant_id=tenant.id,
                provider=PROVIDER_DOCKER,
                resource_type=RESOURCE_TYPE_APP,
                external_id="app-writer",
                display_name="Writer App",
            )
        )


def _login(client) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login", json={"email": "owner@apps.test", "password": "apps-password"}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_catalog_lists_templates(client, monkeypatch):
    asyncio.run(_seed_apps_tenant())

    async def fake_list_templates(self, refresh=False):
        return [
            AppTemplate(
                slug="wordpress-with-mysql", name="WordPress", description="Blog",
                category="cms", tags=["blog"], logo="svgs/wordpress.svg", port="80",
            )
        ]

    monkeypatch.setattr("app.services.app_catalog.AppCatalog.list_templates", fake_list_templates)

    headers = _login(client)
    response = client.get("/api/v1/apps/catalog", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body[0]["slug"] == "wordpress-with-mysql"
    assert body[0]["category"] == "cms"


def test_control_is_tenant_scoped(client, monkeypatch):
    asyncio.run(_seed_apps_tenant())
    monkeypatch.setattr(get_settings(), "enable_provider_actions", True)

    started: list[str] = []

    async def fake_start(self, project):
        started.append(project)
        return {"ok": True, "project": project}

    monkeypatch.setattr("app.services.docker_engine.DockerEngine.start_stack", fake_start)

    headers = _login(client)

    allowed = client.post("/api/v1/apps/app-writer/start", headers=headers)
    assert allowed.status_code == 200

    denied = client.post("/api/v1/apps/app-foreign/start", headers=headers)
    assert denied.status_code == 403

    assert started == ["app-writer"]


def test_install_deploys_and_records_resource(client, monkeypatch):
    asyncio.run(_seed_apps_tenant())
    monkeypatch.setattr(get_settings(), "enable_provider_actions", True)

    compose_b64 = base64.b64encode(b"services:\n  web:\n    image: nginx\n").decode()

    async def fake_get_template(self, slug):
        return AppTemplate(slug=slug, name="WordPress", compose_b64=compose_b64)

    deployed: list[tuple[str, dict]] = []

    async def fake_deploy(self, project, compose_yaml, env=None):
        deployed.append((project, env or {}))
        return {"ok": True, "project": project}

    monkeypatch.setattr("app.services.app_catalog.AppCatalog.get_template", fake_get_template)
    monkeypatch.setattr("app.services.docker_engine.DockerEngine.deploy_stack", fake_deploy)

    headers = _login(client)
    response = client.post(
        "/api/v1/apps/install", headers=headers, json={"slug": "wordpress-with-mysql", "name": "my-blog"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["project"] == "my-blog"
    assert deployed and deployed[0][0] == "my-blog"

    # Installed app is now visible to the tenant.
    listed = client.get("/api/v1/apps", headers=headers)
    assert listed.status_code == 200
    assert any(app["project"] == "my-blog" for app in listed.json())

    # ...and it also shows in the deployments history, marked as an app install.
    deploys = client.get("/api/v1/deploys", headers=headers)
    assert deploys.status_code == 200
    app_dep = next((d for d in deploys.json() if d["project"] == "my-blog"), None)
    assert app_dep is not None and app_dep["builder"] == "app" and app_dep["status"] == "ready"


def test_install_blocked_when_actions_disabled(client, monkeypatch):
    asyncio.run(_seed_apps_tenant())
    monkeypatch.setattr(get_settings(), "enable_provider_actions", False)

    headers = _login(client)
    response = client.post("/api/v1/apps/install", headers=headers, json={"slug": "whatever"})
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Quota enforcement tests (Task 3.3 + 3.4)
# ---------------------------------------------------------------------------

async def _seed_quota_tenant(max_apps: int = 1, already_installed: int = 0) -> None:
    """Seed a tenant on a plan with max_apps=<max_apps> and optionally some installed apps."""
    async with session_scope() as session:
        auth_service = AuthService(session)
        plan = Plan(
            key=f"quota_plan_{max_apps}",
            name=f"Quota Plan {max_apps}",
            max_apps=max_apps,
            max_domains=0,
            cpu_millicores=500,
            mem_mb=512,
            disk_mb=2048,
        )
        session.add(plan)
        await session.flush()

        tenant = Tenant(name="Quota Tenant", slug="quota-t", status="active", plan_id=plan.id)
        session.add(tenant)
        await session.flush()

        session.add(
            AdminUser(
                tenant_id=tenant.id,
                email="owner@quota.test",
                full_name="Quota Owner",
                password_hash=auth_service.hash_password("quota-pass"),
                is_active=True,
            )
        )
        for i in range(already_installed):
            session.add(
                TenantResource(
                    tenant_id=tenant.id,
                    provider=PROVIDER_DOCKER,
                    resource_type=RESOURCE_TYPE_APP,
                    external_id=f"existing-app-{i}",
                    display_name=f"Existing App {i}",
                )
            )


def _login_quota(client) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login", json={"email": "owner@quota.test", "password": "quota-pass"}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_install_over_quota_returns_402(client, monkeypatch):
    """POST /api/v1/apps/install on a max_apps=1 tenant that already has 1 app → 402."""
    asyncio.run(_seed_quota_tenant(max_apps=1, already_installed=1))
    monkeypatch.setattr(get_settings(), "enable_provider_actions", True)

    compose_b64 = base64.b64encode(b"services:\n  web:\n    image: nginx\n").decode()

    async def fake_get_template(self, slug):
        return AppTemplate(slug=slug, name="Test App", compose_b64=compose_b64)

    async def fake_deploy(self, project, compose_yaml, env=None):
        return {"ok": True, "project": project}

    monkeypatch.setattr("app.services.app_catalog.AppCatalog.get_template", fake_get_template)
    monkeypatch.setattr("app.services.docker_engine.DockerEngine.deploy_stack", fake_deploy)

    headers = _login_quota(client)
    response = client.post(
        "/api/v1/apps/install", headers=headers, json={"slug": "test-app", "name": "new-app"}
    )
    assert response.status_code == 402, response.text
    body = response.json()
    assert body["error"] == "quota_exceeded"
    assert body["reason"] == "apps"
    assert body["limit"] == 1
    assert body["used"] == 1


def test_install_failure_releases_reservation(client, monkeypatch):
    """If engine.deploy_stack raises DockerEngineError, the quota reservation is released (no orphan)."""
    asyncio.run(_seed_quota_tenant(max_apps=2, already_installed=0))
    monkeypatch.setattr(get_settings(), "enable_provider_actions", True)

    compose_b64 = base64.b64encode(b"services:\n  web:\n    image: nginx\n").decode()

    async def fake_get_template(self, slug):
        return AppTemplate(slug=slug, name="Test App", compose_b64=compose_b64)

    from app.services.docker_engine import DockerEngineError as _DockerEngineError

    async def failing_deploy(self, project, compose_yaml, env=None):
        raise _DockerEngineError(message="simulated engine failure", code=500)

    monkeypatch.setattr("app.services.app_catalog.AppCatalog.get_template", fake_get_template)
    monkeypatch.setattr("app.services.docker_engine.DockerEngine.deploy_stack", failing_deploy)

    headers = _login_quota(client)
    response = client.post(
        "/api/v1/apps/install", headers=headers, json={"slug": "test-app", "name": "failed-app"}
    )
    # Engine failure → 500 (mapped from DockerEngineError code=500)
    assert response.status_code in (500, 503), response.text

    # Tightened assertion: directly count TenantResource rows (resource_type=app) for
    # this tenant — avoids masking a silently-failed release via the usage() composite count.
    async def check_resource_rows():
        from sqlalchemy import func, select
        async with session_scope() as session:
            from app.models import Tenant
            tenant = (await session.scalars(select(Tenant).where(Tenant.slug == "quota-t"))).first()
            count = await session.scalar(
                select(func.count()).where(
                    TenantResource.tenant_id == tenant.id,
                    TenantResource.resource_type == RESOURCE_TYPE_APP,
                )
            )
            return count or 0

    row_count = asyncio.run(check_resource_rows())
    assert row_count == 0, f"Expected 0 TenantResource app rows after failure, got {row_count}"


def test_install_non_docker_error_releases_reservation(client, monkeypatch):
    """If engine.deploy_stack raises a NON-DockerEngineError (e.g. RuntimeError, TimeoutError),
    the quota reservation must still be released — no orphan quota slot.

    RED before Fix 1 (narrow except DockerEngineError): RuntimeError propagates without release,
    TenantResource count stays 1.
    GREEN after Fix 1 (broad except Exception): reservation released, count back to 0.

    The RuntimeError propagates through the FastAPI route (which catches only DockerEngineError)
    and is re-raised by TestClient. We catch it here and then verify the row count.
    """
    import pytest

    asyncio.run(_seed_quota_tenant(max_apps=2, already_installed=0))
    monkeypatch.setattr(get_settings(), "enable_provider_actions", True)

    compose_b64 = base64.b64encode(b"services:\n  web:\n    image: nginx\n").decode()

    async def fake_get_template(self, slug):
        return AppTemplate(slug=slug, name="Test App", compose_b64=compose_b64)

    async def crashing_deploy(self, project, compose_yaml, env=None):
        raise RuntimeError("boom — unexpected non-engine error")

    monkeypatch.setattr("app.services.app_catalog.AppCatalog.get_template", fake_get_template)
    monkeypatch.setattr("app.services.docker_engine.DockerEngine.deploy_stack", crashing_deploy)

    headers = _login_quota(client)

    # The RuntimeError is not caught by the route handler, so TestClient re-raises it.
    # This proves (a) the install fails — it does not silently swallow the error.
    with pytest.raises(RuntimeError, match="boom"):
        client.post(
            "/api/v1/apps/install", headers=headers, json={"slug": "test-app", "name": "crash-app"}
        )

    # (b) Direct TenantResource row count must be 0 — reservation released despite non-DockerEngineError.
    async def check_resource_rows():
        from sqlalchemy import func, select
        async with session_scope() as session:
            from app.models import Tenant
            tenant = (await session.scalars(select(Tenant).where(Tenant.slug == "quota-t"))).first()
            count = await session.scalar(
                select(func.count()).where(
                    TenantResource.tenant_id == tenant.id,
                    TenantResource.resource_type == RESOURCE_TYPE_APP,
                )
            )
            return count or 0

    row_count = asyncio.run(check_resource_rows())
    assert row_count == 0, (
        f"Expected 0 TenantResource app rows after RuntimeError, got {row_count} — "
        "reservation leaked (Fix 1 not applied)"
    )


def test_git_deploy_duplicate_name_returns_409(client, monkeypatch):
    """POST /api/v1/deploys/git with a name matching an existing TenantResource → 409.

    D4: start_deploy_for_tenant must pre-check for an existing app with the same
    project name (external_id) for the tenant before reserving quota or starting
    a build. This prevents two TenantResource rows for the same project.
    """
    asyncio.run(_seed_apps_tenant())
    monkeypatch.setattr(get_settings(), "enable_provider_actions", True)

    # app-writer is already seeded as a TenantResource in _seed_apps_tenant().
    async def fake_build(self, git_url, ref, *, project, on_line=None):
        raise AssertionError("build should not be reached when duplicate is detected")

    async def fake_deploy(self, project, compose_yaml, env=None):
        raise AssertionError("deploy should not be reached when duplicate is detected")

    monkeypatch.setattr("app.services.builder.Builder.build_from_git", fake_build)
    monkeypatch.setattr("app.services.docker_engine.DockerEngine.deploy_stack", fake_deploy)

    headers = _login(client)
    response = client.post(
        "/api/v1/deploys/git",
        headers=headers,
        json={"git_url": "https://github.com/example/repo.git", "ref": "main", "name": "app-writer", "port": 3000},
    )
    assert response.status_code == 409, response.text

    # Confirm no extra TenantResource row was created.
    async def count_rows():
        from sqlalchemy import func, select as sa_select
        async with session_scope() as session:
            from app.models import Tenant
            tenant = (await session.scalars(sa_select(Tenant).where(Tenant.slug == "appst"))).first()
            return await session.scalar(
                sa_select(func.count()).where(
                    TenantResource.tenant_id == tenant.id,
                    TenantResource.resource_type == RESOURCE_TYPE_APP,
                )
            ) or 0

    assert asyncio.run(count_rows()) == 1, "Expected exactly 1 TenantResource row (no duplicate created)"


def test_pending_tenant_gets_403_not_402(client, monkeypatch):
    """A pending (non-active) tenant hitting install must get 403 from the status gate,
    NOT 402 from quota enforcement — gate precedence is locked."""

    async def _seed_pending_tenant():
        async with session_scope() as session:
            auth_service = AuthService(session)
            tenant = Tenant(name="Pending Corp", slug="pending-corp", status="pending")
            session.add(tenant)
            await session.flush()
            session.add(
                AdminUser(
                    tenant_id=tenant.id,
                    email="owner@pending.test",
                    full_name="Pending Owner",
                    password_hash=auth_service.hash_password("pend-pass"),
                    is_active=True,
                )
            )

    asyncio.run(_seed_pending_tenant())
    monkeypatch.setattr(get_settings(), "enable_provider_actions", True)

    response = client.post(
        "/api/v1/auth/login", json={"email": "owner@pending.test", "password": "pend-pass"}
    )
    assert response.status_code == 200
    headers = {"Authorization": f"Bearer {response.json()['token']}"}

    response = client.post(
        "/api/v1/apps/install", headers=headers, json={"slug": "test-app", "name": "blocked-app"}
    )
    assert response.status_code == 403, (
        f"Expected 403 from status gate, got {response.status_code}: {response.text}"
    )
