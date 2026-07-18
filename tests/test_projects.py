"""Projects read surface: tenant-scoped listing + pagination contract."""

import asyncio

from app.db import session_scope
from app.models import AdminUser, Tenant, TenantResource
from app.models.tenant_resource import PROVIDER_COOLIFY, RESOURCE_TYPE_SITE
from app.modules.auth.service import AuthService
from app.services.coolify import CoolifyApplication


def _app(app_id: str, name: str) -> CoolifyApplication:
    return CoolifyApplication(
        id=app_id,
        name=name,
        primary_domain=f"{name}.test",
        status="running",
        repository="",
        environment="production",
        updated_at="2026-01-01T00:00:00Z",
    )


APPS = [_app("app-one", "one"), _app("app-two", "two"), _app("app-three", "three")]


async def _seed_projects_tenant() -> None:
    async with session_scope() as session:
        auth_service = AuthService(session)
        tenant = Tenant(name="Proj Tenant", slug="projtenant", status="active")
        session.add(tenant)
        await session.flush()
        session.add(
            AdminUser(
                tenant_id=tenant.id,
                email="owner@projtenant.test",
                full_name="Proj Owner",
                password_hash=auth_service.hash_password("proj-password"),
                is_active=True,
            )
        )
        session.add_all(
            [
                TenantResource(
                    tenant_id=tenant.id,
                    provider=PROVIDER_COOLIFY,
                    resource_type=RESOURCE_TYPE_SITE,
                    external_id="app-one",
                    display_name="one",
                ),
                TenantResource(
                    tenant_id=tenant.id,
                    provider=PROVIDER_COOLIFY,
                    resource_type=RESOURCE_TYPE_SITE,
                    external_id="app-two",
                    display_name="two",
                ),
            ]
        )


def _login(client, email: str = "owner@projtenant.test", password: str = "proj-password"):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def _mock_coolify(monkeypatch) -> None:
    async def fake_list_applications(self, refresh=False):
        return APPS

    monkeypatch.setattr(
        "app.services.coolify.CoolifyClient.list_applications", fake_list_applications
    )


def test_projects_listing_is_tenant_scoped(client, monkeypatch):
    asyncio.run(_seed_projects_tenant())
    _mock_coolify(monkeypatch)

    response = client.get("/api/v1/projects", headers=_login(client))
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert ids == ["app-one", "app-two"]  # app-three belongs to no tenant resource


def test_projects_platform_admin_sees_all(client, monkeypatch):
    _mock_coolify(monkeypatch)

    headers = _login(client, email="admin@example.com", password="supersecurepassword")
    response = client.get("/api/v1/projects", headers=headers)
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == ["app-one", "app-two", "app-three"]


def test_projects_listing_paginates(client, monkeypatch):
    _mock_coolify(monkeypatch)

    headers = _login(client, email="admin@example.com", password="supersecurepassword")
    response = client.get("/api/v1/projects", params={"limit": 1, "offset": 1}, headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert [item["id"] for item in payload] == ["app-two"]
    assert response.headers.get("X-Total-Count") == "3"
