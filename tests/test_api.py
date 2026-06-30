import asyncio
from uuid import uuid4

from app.db import session_scope
from app.models import AdminUser, Tenant, TenantResource
from app.models.tenant_resource import (
    PROVIDER_CLOUDFLARE,
    PROVIDER_COOLIFY,
    PROVIDER_MAILCOW,
    RESOURCE_TYPE_DNS_ZONE,
    RESOURCE_TYPE_MAIL_DOMAIN,
    RESOURCE_TYPE_SITE,
)
from app.modules.auth.service import AuthService
from app.services.cloudflare import CloudflareDNSRecord, CloudflareZone
from app.services.coolify import CoolifyApplication
from app.services.mailcow import MailcowDomain, MailcowMailbox


def test_api_login_and_me(client):
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@example.com",
            "password": "supersecurepassword",
        },
    )
    assert login_response.status_code == 200
    payload = login_response.json()
    assert payload["admin"]["email"] == "admin@example.com"
    assert payload["admin"]["tenant_slug"] == "default"
    assert payload["token"]

    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {payload['token']}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "admin@example.com"
    assert me_response.json()["tenant_slug"] == "default"


def test_api_protected_routes_require_auth(client):
    response = client.get("/api/v1/dashboard")
    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required."


def test_api_dashboard_returns_metrics(client):
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@example.com",
            "password": "supersecurepassword",
        },
    )
    token = login_response.json()["token"]
    response = client.get("/api/v1/dashboard", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    payload = response.json()
    assert "providers" in payload
    assert "metrics" in payload
    assert payload["metrics"]["admins"] >= 1


def test_api_admin_is_tenant_aware(client):
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@example.com",
            "password": "supersecurepassword",
        },
    )
    token = login_response.json()["token"]
    response = client.get("/api/v1/admin", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["admins"]
    assert all(admin["tenant_slug"] == "default" for admin in payload["admins"])


def test_api_can_create_tenant_admin_and_resource(client):
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@example.com",
            "password": "supersecurepassword",
        },
    )
    token = login_response.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    tenant_response = client.post(
        "/api/v1/tenants",
        headers=headers,
        json={"name": "API Tenant", "slug": "api-tenant"},
    )
    assert tenant_response.status_code == 200
    assert tenant_response.json()["slug"] == "api-tenant"

    admin_response = client.post(
        "/api/v1/tenant-admins",
        headers=headers,
        json={
            "tenant_slug": "api-tenant",
            "email": "owner@api-tenant.test",
            "full_name": "API Tenant Owner",
            "password": "owner-password",
        },
    )
    assert admin_response.status_code == 200
    assert admin_response.json()["email"] == "owner@api-tenant.test"
    assert admin_response.json()["tenant_slug"] == "api-tenant"

    resource_response = client.post(
        "/api/v1/tenant-resources",
        headers=headers,
        json={
            "tenant_slug": "api-tenant",
            "provider": "cloudflare",
            "resource_type": "dns_zone",
            "external_id": "zone-api-tenant",
            "display_name": "API Tenant Zone",
        },
    )
    assert resource_response.status_code == 200
    assert resource_response.json()["external_id"] == "zone-api-tenant"
    assert resource_response.json()["tenant_slug"] == "api-tenant"


def test_api_lists_tenants_and_can_toggle_activation(client):
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@example.com",
            "password": "supersecurepassword",
        },
    )
    token = login_response.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    tenant_response = client.post(
        "/api/v1/tenants",
        headers=headers,
        json={"name": "Toggle Tenant", "slug": "toggle-tenant"},
    )
    assert tenant_response.status_code == 200

    list_response = client.get("/api/v1/tenants", headers=headers)
    assert list_response.status_code == 200
    assert any(tenant["slug"] == "toggle-tenant" for tenant in list_response.json())

    deactivate_response = client.post("/api/v1/tenants/toggle-tenant/deactivate", headers=headers)
    assert deactivate_response.status_code == 200
    assert deactivate_response.json()["is_active"] is False

    activate_response = client.post("/api/v1/tenants/toggle-tenant/activate", headers=headers)
    assert activate_response.status_code == 200
    assert activate_response.json()["is_active"] is True



def test_api_deploy_is_limited_to_tenant_resources(client, monkeypatch):
    asyncio.run(_seed_tenant_resources())

    deploy_calls: list[str] = []

    async def fake_deploy_application(self, application_uuid: str, force: bool = False, tag: str = ""):
        deploy_calls.append(application_uuid)
        return {"ok": True, "message": f"Deployment queued for {application_uuid}"}

    monkeypatch.setattr("app.services.coolify.CoolifyClient.deploy_application", fake_deploy_application)

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "owner@acme.test",
            "password": "acme-password",
        },
    )
    assert login_response.status_code == 200
    token = login_response.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    allowed_response = client.post("/api/v1/projects/app-acme/deploy", headers=headers)
    assert allowed_response.status_code == 200
    assert allowed_response.json()["message"] == "Deployment queued for app-acme"

    denied_response = client.post("/api/v1/projects/app-other/deploy", headers=headers)
    assert denied_response.status_code == 403
    assert denied_response.json()["detail"] == "Application is not assigned to this tenant."

    assert deploy_calls == ["app-acme"]



def test_api_site_actions_and_deployments_are_tenant_scoped(client, monkeypatch):
    asyncio.run(_seed_tenant_resources())

    start_calls: list[str] = []
    restart_calls: list[str] = []
    deployment_calls: list[str] = []

    async def fake_start_application(self, application_uuid: str):
        start_calls.append(application_uuid)
        return {"ok": True, "message": f"Start requested for {application_uuid}"}

    async def fake_restart_application(self, application_uuid: str):
        restart_calls.append(application_uuid)
        return {"ok": True, "message": f"Restart requested for {application_uuid}"}

    async def fake_list_deployments(self, application_uuid: str):
        deployment_calls.append(application_uuid)
        return [
            {
                "id": "dep-1",
                "status": "finished",
                "created_at": "2026-06-27T00:00:00Z",
                "updated_at": "2026-06-27T00:05:00Z",
                "commit": "abc123",
                "branch": "main",
            }
        ]

    from app.services.coolify import CoolifyDeployment
    async def fake_list_deployments_model(self, application_uuid: str):
        deployment_calls.append(application_uuid)
        return [CoolifyDeployment(id="dep-1", status="finished", created_at="2026-06-27T00:00:00Z", updated_at="2026-06-27T00:05:00Z", commit="abc123", branch="main")]

    monkeypatch.setattr("app.services.coolify.CoolifyClient.start_application", fake_start_application)
    monkeypatch.setattr("app.services.coolify.CoolifyClient.restart_application", fake_restart_application)
    monkeypatch.setattr("app.services.coolify.CoolifyClient.list_deployments_for_application", fake_list_deployments_model)

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "owner@acme.test",
            "password": "acme-password",
        },
    )
    assert login_response.status_code == 200
    token = login_response.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    start_response = client.post("/api/v1/projects/app-acme/start", headers=headers)
    assert start_response.status_code == 200
    assert start_response.json()["message"] == "Start requested for app-acme"

    restart_response = client.post("/api/v1/projects/app-acme/restart", headers=headers)
    assert restart_response.status_code == 200
    assert restart_response.json()["message"] == "Restart requested for app-acme"

    deployments_response = client.get("/api/v1/projects/app-acme/deployments", headers=headers)
    assert deployments_response.status_code == 200
    assert deployments_response.json()[0]["id"] == "dep-1"

    denied_start = client.post("/api/v1/projects/app-other/start", headers=headers)
    denied_restart = client.post("/api/v1/projects/app-other/restart", headers=headers)
    denied_deployments = client.get("/api/v1/projects/app-other/deployments", headers=headers)
    assert denied_start.status_code == 403
    assert denied_restart.status_code == 403
    assert denied_deployments.status_code == 403

    assert start_calls == ["app-acme"]
    assert restart_calls == ["app-acme"]
    assert deployment_calls == ["app-acme"]


async def _seed_tenant_resources() -> None:
    async with session_scope() as session:
        auth_service = AuthService(session)
        tenant = Tenant(name="Acme Tenant", slug="acme", status="active")
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

        session.add_all(
            [
                TenantResource(
                    tenant_id=tenant.id,
                    provider=PROVIDER_COOLIFY,
                    resource_type=RESOURCE_TYPE_SITE,
                    external_id="app-acme",
                    display_name="Acme App",
                ),
                TenantResource(
                    tenant_id=tenant.id,
                    provider=PROVIDER_MAILCOW,
                    resource_type=RESOURCE_TYPE_MAIL_DOMAIN,
                    external_id="acme.test",
                    display_name="acme.test",
                ),
                TenantResource(
                    tenant_id=tenant.id,
                    provider=PROVIDER_CLOUDFLARE,
                    resource_type=RESOURCE_TYPE_DNS_ZONE,
                    external_id="zone-acme",
                    display_name="acme.test",
                ),
            ]
        )


async def _provider_fixtures() -> tuple[
    list[CoolifyApplication],
    list[MailcowDomain],
    list[MailcowMailbox],
    list[CloudflareZone],
    list[CloudflareDNSRecord],
]:
    return (
        [
            CoolifyApplication(
                id="app-acme",
                name="Acme App",
                primary_domain="app.acme.test",
                status="running",
                repository="git@example.com/acme/app",
                environment="production",
                updated_at="2026-06-27T00:00:00Z",
            ),
            CoolifyApplication(
                id=f"app-other-{uuid4()}",
                name="Other App",
                primary_domain="other.test",
                status="running",
                repository="git@example.com/other/app",
                environment="production",
                updated_at="2026-06-27T00:00:00Z",
            ),
        ],
        [
            MailcowDomain(domain_name="acme.test", mailboxes=3, aliases=1, quota_bytes=1000, active=True),
            MailcowDomain(domain_name="other.test", mailboxes=2, aliases=0, quota_bytes=1000, active=True),
        ],
        [
            MailcowMailbox(
                username="owner@acme.test",
                name="Owner",
                domain="acme.test",
                quota_bytes=1000,
                messages=1,
                active=True,
            ),
            MailcowMailbox(
                username="ops@other.test",
                name="Ops",
                domain="other.test",
                quota_bytes=1000,
                messages=1,
                active=True,
            ),
        ],
        [
            CloudflareZone(id="zone-acme", name="acme.test", status="active", account_name="Acme", paused=False),
            CloudflareZone(id="zone-other", name="other.test", status="active", account_name="Other", paused=False),
        ],
        [
            CloudflareDNSRecord(
                id="rec-acme",
                type="A",
                name="app.acme.test",
                content="1.2.3.4",
                ttl=1,
                proxied=True,
            ),
            CloudflareDNSRecord(
                id="rec-other",
                type="A",
                name="app.other.test",
                content="5.6.7.8",
                ttl=1,
                proxied=False,
            ),
        ],
    )


def test_api_provider_data_is_filtered_by_tenant(client, monkeypatch):
    asyncio.run(_seed_tenant_resources())
    sites, domains, mailboxes, zones, records = asyncio.run(_provider_fixtures())

    async def fake_list_applications(self, refresh: bool = False):
        return sites

    async def fake_list_domains(self, refresh: bool = False):
        return domains

    async def fake_list_mailboxes(self, refresh: bool = False):
        return mailboxes

    async def fake_list_zones(self, refresh: bool = False):
        return zones

    async def fake_list_dns_records(self, zone_id: str, refresh: bool = False):
        return records if zone_id == "zone-acme" else []

    monkeypatch.setattr("app.services.coolify.CoolifyClient.list_applications", fake_list_applications)
    monkeypatch.setattr("app.services.mailcow.MailcowClient.list_domains", fake_list_domains)
    monkeypatch.setattr("app.services.mailcow.MailcowClient.list_mailboxes", fake_list_mailboxes)
    monkeypatch.setattr("app.services.cloudflare.CloudflareClient.list_zones", fake_list_zones)
    monkeypatch.setattr("app.services.cloudflare.CloudflareClient.list_dns_records", fake_list_dns_records)

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "owner@acme.test",
            "password": "acme-password",
        },
    )
    assert login_response.status_code == 200
    token = login_response.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    sites_response = client.get("/api/v1/projects", headers=headers)
    assert sites_response.status_code == 200
    assert [site["id"] for site in sites_response.json()] == ["app-acme"]

    mail_response = client.get("/api/v1/mail", headers=headers)
    assert mail_response.status_code == 200
    assert [domain["domain_name"] for domain in mail_response.json()["domains"]] == ["acme.test"]
    assert [mailbox["username"] for mailbox in mail_response.json()["mailboxes"]] == ["owner@acme.test"]

    dns_response = client.get("/api/v1/dns", headers=headers)
    assert dns_response.status_code == 200
    payload = dns_response.json()
    assert [zone["id"] for zone in payload["zones"]] == ["zone-acme"]
    assert payload["selected_zone"] == "zone-acme"
    assert [record["name"] for record in payload["records"]] == ["app.acme.test"]

    dashboard_response = client.get("/api/v1/dashboard", headers=headers)
    assert dashboard_response.status_code == 200
    metrics = dashboard_response.json()["metrics"]
    assert metrics["projects"] == 1
    assert metrics["mail_domains"] == 1
    assert metrics["dns_zones"] == 1
