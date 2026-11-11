import asyncio

from app.db import session_scope
from app.models import AdminUser, Tenant, TenantResource
from app.models.tenant_resource import (
    PROVIDER_CLOUDFLARE,
    PROVIDER_DOCKER,
    PROVIDER_MAILCOW,
    RESOURCE_TYPE_APP,
    RESOURCE_TYPE_DNS_ZONE,
    RESOURCE_TYPE_MAIL_DOMAIN,
)
from app.modules.auth.service import AuthService
from app.services.cloudflare import CloudflareDNSRecord, CloudflareZone
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

    # Coolify apps are imported, not assigned.
    coolify_response = client.post(
        "/api/v1/tenant-resources",
        headers=headers,
        json={
            "tenant_slug": "api-tenant",
            "provider": "coolify",
            "resource_type": "site",
            "external_id": "app-uuid",
            "display_name": "Old site",
        },
    )
    assert coolify_response.status_code == 400


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
                    provider=PROVIDER_DOCKER,
                    resource_type=RESOURCE_TYPE_APP,
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
    list[MailcowDomain],
    list[MailcowMailbox],
    list[CloudflareZone],
    list[CloudflareDNSRecord],
]:
    return (
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
    domains, mailboxes, zones, records = asyncio.run(_provider_fixtures())

    async def fake_list_domains(self, refresh: bool = False):
        return domains

    async def fake_list_mailboxes(self, refresh: bool = False):
        return mailboxes

    async def fake_list_zones(self, refresh: bool = False):
        return zones

    async def fake_list_dns_records(self, zone_id: str, refresh: bool = False):
        return records if zone_id == "zone-acme" else []

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
