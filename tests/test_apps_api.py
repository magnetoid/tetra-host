import asyncio
import base64

from app.config import get_settings
from app.db import session_scope
from app.models import AdminUser, Tenant, TenantResource
from app.models.tenant_resource import PROVIDER_DOCKER, RESOURCE_TYPE_APP
from app.modules.auth.service import AuthService
from app.services.app_catalog import AppTemplate


async def _seed_apps_tenant() -> None:
    async with session_scope() as session:
        auth_service = AuthService(session)
        tenant = Tenant(name="Apps Tenant", slug="appst", is_active=True)
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


def test_install_blocked_when_actions_disabled(client, monkeypatch):
    asyncio.run(_seed_apps_tenant())
    monkeypatch.setattr(get_settings(), "enable_provider_actions", False)

    headers = _login(client)
    response = client.post("/api/v1/apps/install", headers=headers, json={"slug": "whatever"})
    assert response.status_code == 403
