import asyncio
import re

from app.config import get_settings
from app.db import session_scope
from app.models import AdminUser, Tenant, TenantResource
from app.models.tenant_resource import PROVIDER_COOLIFY, RESOURCE_TYPE_SITE
from app.modules.auth.service import AuthService
from app.services.coolify import CoolifyApplication, normalize_coolify_resource


def test_ready_exposes_provider_configuration_flags(client):
    data = client.get("/ready").json()
    assert data["ok"] is True
    assert "coolify" in data["providers"]
    assert "mailcow" in data["providers"]


def test_coolify_resource_normalization_supports_common_shapes():
    raw = {
        'uuid': 'abc123',
        'name': 'Production API',
        'fqdn': 'https://api.example.com,https://www.api.example.com',
        'status': 'running',
        'git_repository': 'magnetoid/api',
        "environment_name": "production",
        "updated_at": "2026-06-26T12:00:00Z",
        "build_pack": "dockerfile",
        "health_check_enabled": True,
    }
    app_item = normalize_coolify_resource(raw)
    assert isinstance(app_item, CoolifyApplication)
    assert app_item.id == "abc123"
    assert app_item.primary_domain == "api.example.com"
    assert app_item.status == "running"
    assert app_item.repository == "magnetoid/api"
    assert app_item.environment == "production"
    assert app_item.build_pack == "dockerfile"
    assert app_item.healthcheck_enabled is True


def test_sites_page_requires_auth(client):
    response = client.get("/sites", follow_redirects=False)
    assert response.status_code == 303


def test_dashboard_renders_operational_copy_for_authenticated_admin(authenticated_client):
    html = authenticated_client.get("/dashboard").text
    assert "PaaS Overview" in html
    assert "Provider connectivity" in html
    assert "Refresh providers" in html
    assert "Not configured" in html


def extract_csrf_token(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match is not None
    return match.group(1)


async def _seed_site_tenant() -> None:
    async with session_scope() as session:
        auth_service = AuthService(session)
        tenant = Tenant(name="Acme Tenant", slug="acme", is_active=True)
        session.add(tenant)
        await session.flush()

        admin = AdminUser(
            tenant_id=tenant.id,
            email="owner@acme.test",
            full_name="Acme Owner",
            password_hash=auth_service.hash_password("acme-password"),
            is_active=True,
        )
        session.add(admin)
        await session.flush()

        session.add(
            TenantResource(
                tenant_id=tenant.id,
                provider=PROVIDER_COOLIFY,
                resource_type=RESOURCE_TYPE_SITE,
                external_id="app-acme",
                display_name="Acme App",
            )
        )


def test_sites_deploy_action_is_tenant_scoped(client, monkeypatch):
    asyncio.run(_seed_site_tenant())
    monkeypatch.setattr(get_settings(), "enable_provider_actions", True)

    deploy_calls: list[str] = []

    async def fake_deploy_application(self, application_uuid: str, force: bool = False):
        deploy_calls.append(application_uuid)
        return {"ok": True, "message": f"Deployment queued for {application_uuid}"}

    monkeypatch.setattr("app.services.coolify.CoolifyClient.deploy_application", fake_deploy_application)

    login_page = client.get("/auth/login")
    csrf_token = extract_csrf_token(login_page.text)
    login_response = client.post(
        "/auth/login",
        data={
            "email": "owner@acme.test",
            "password": "***",
            "csrf_token": csrf_token,
            "next_url": "/sites",
        },
        follow_redirects=False,
    )
    assert login_response.status_code == 303

    sites_page = client.get("/sites")
    page_csrf = extract_csrf_token(sites_page.text)

    allowed_response = client.post(
        "/sites/app-acme/deploy",
        data={"csrf_token": page_csrf},
        follow_redirects=False,
    )
    assert allowed_response.status_code == 303
    assert allowed_response.headers["location"].endswith("/sites?deploy=Deployment%20queued%20for%20app-acme")

    denied_response = client.post(
        "/sites/app-other/deploy",
        data={"csrf_token": page_csrf},
        follow_redirects=False,
    )
    assert denied_response.status_code == 303
    assert denied_response.headers["location"].endswith(
        "/sites?deploy_error=Application%20is%20not%20assigned%20to%20this%20tenant."
    )

    assert deploy_calls == ["app-acme"]



def test_sites_start_restart_and_deployments_are_tenant_scoped(client, monkeypatch):
    asyncio.run(_seed_site_tenant())
    monkeypatch.setattr(get_settings(), "enable_provider_actions", True)

    start_calls: list[str] = []
    restart_calls: list[str] = []
    deployment_calls: list[str] = []

    async def fake_start_application(self, application_uuid: str):
        start_calls.append(application_uuid)
        return {"ok": True, "message": f"Start requested for {application_uuid}"}

    async def fake_restart_application(self, application_uuid: str):
        restart_calls.append(application_uuid)
        return {"ok": True, "message": f"Restart requested for {application_uuid}"}

    from app.services.coolify import CoolifyDeployment
    async def fake_list_deployments_model(self, application_uuid: str):
        deployment_calls.append(application_uuid)
        return [CoolifyDeployment(id="dep-1", status="finished", created_at="2026-06-27T00:00:00Z", updated_at="2026-06-27T00:05:00Z", commit="abc123", branch="main")]

    monkeypatch.setattr("app.services.coolify.CoolifyClient.start_application", fake_start_application)
    monkeypatch.setattr("app.services.coolify.CoolifyClient.restart_application", fake_restart_application)
    monkeypatch.setattr("app.services.coolify.CoolifyClient.list_deployments_for_application", fake_list_deployments_model)

    login_page = client.get("/auth/login")
    csrf_token = extract_csrf_token(login_page.text)
    login_response = client.post(
        "/auth/login",
        data={
            "email": "owner@acme.test",
            "password": "***",
            "csrf_token": csrf_token,
            "next_url": "/sites",
        },
        follow_redirects=False,
    )
    assert login_response.status_code == 303

    sites_page = client.get("/sites")
    page_csrf = extract_csrf_token(sites_page.text)

    start_response = client.post("/sites/app-acme/start", data={"csrf_token": page_csrf}, follow_redirects=False)
    restart_response = client.post("/sites/app-acme/restart", data={"csrf_token": page_csrf}, follow_redirects=False)
    assert start_response.status_code == 303
    assert restart_response.status_code == 303
    assert start_response.headers["location"].endswith("/sites?start=Start%20requested%20for%20app-acme")
    assert restart_response.headers["location"].endswith("/sites?restart=Restart%20requested%20for%20app-acme")

    denied_start = client.post("/sites/app-other/start", data={"csrf_token": page_csrf}, follow_redirects=False)
    denied_restart = client.post("/sites/app-other/restart", data={"csrf_token": page_csrf}, follow_redirects=False)
    assert denied_start.headers["location"].endswith("/sites?start_error=Application%20is%20not%20assigned%20to%20this%20tenant.")
    assert denied_restart.headers["location"].endswith("/sites?restart_error=Application%20is%20not%20assigned%20to%20this%20tenant.")

    deployments_page = client.get("/sites?app=app-acme")
    assert deployments_page.status_code == 200
    assert "Recent deployments" in deployments_page.text
    assert "dep-1" in deployments_page.text

    denied_deployments_page = client.get("/sites?app=app-other")
    assert denied_deployments_page.status_code == 200
    assert "Application is not assigned to this tenant." in denied_deployments_page.text

    assert start_calls == ["app-acme"]
    assert restart_calls == ["app-acme"]
    assert deployment_calls == ["app-acme"]