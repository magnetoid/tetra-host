import asyncio

from app.db import session_scope
from app.models import AdminUser, Tenant, TenantResource
from app.models.tenant_resource import (
    PROVIDER_CLOUDFLARE,
    PROVIDER_COOLIFY,
    RESOURCE_TYPE_DNS_ZONE,
    RESOURCE_TYPE_SITE,
)
from app.modules.auth.service import AuthService


async def _seed_writer_tenant() -> None:
    async with session_scope() as session:
        auth_service = AuthService(session)
        tenant = Tenant(name="Writer Tenant", slug="writer", is_active=True)
        session.add(tenant)
        await session.flush()
        session.add(
            AdminUser(
                tenant_id=tenant.id,
                email="owner@writer.test",
                full_name="Writer Owner",
                password_hash=auth_service.hash_password("writer-password"),
                is_active=True,
            )
        )
        session.add_all(
            [
                TenantResource(
                    tenant_id=tenant.id,
                    provider=PROVIDER_CLOUDFLARE,
                    resource_type=RESOURCE_TYPE_DNS_ZONE,
                    external_id="zone-writer",
                    display_name="writer.test",
                ),
                TenantResource(
                    tenant_id=tenant.id,
                    provider=PROVIDER_COOLIFY,
                    resource_type=RESOURCE_TYPE_SITE,
                    external_id="app-writer",
                    display_name="Writer App",
                ),
            ]
        )


def _login(client) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@writer.test", "password": "writer-password"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_create_dns_record_is_tenant_scoped(client, monkeypatch):
    asyncio.run(_seed_writer_tenant())

    created: list[str] = []

    async def fake_create_dns_record(self, zone_id, record_type, name, content, ttl=1, proxied=False, priority=None):
        created.append(zone_id)
        return {"ok": True}

    monkeypatch.setattr("app.services.cloudflare.CloudflareClient.create_dns_record", fake_create_dns_record)

    headers = _login(client)
    body = {"type": "A", "name": "app.writer.test", "content": "1.2.3.4", "ttl": 1, "proxied": False}

    allowed = client.post("/api/v1/dns/zones/zone-writer/records", headers=headers, json=body)
    assert allowed.status_code == 200
    assert allowed.json()["message"] == "DNS record created."

    denied = client.post("/api/v1/dns/zones/zone-foreign/records", headers=headers, json=body)
    assert denied.status_code == 403
    assert denied.json()["detail"] == "Zone is not assigned to this tenant."

    assert created == ["zone-writer"]


def test_delete_dns_record_is_tenant_scoped(client, monkeypatch):
    asyncio.run(_seed_writer_tenant())

    deleted: list[tuple[str, str]] = []

    async def fake_delete_dns_record(self, zone_id, record_id):
        deleted.append((zone_id, record_id))
        return {"ok": True}

    monkeypatch.setattr("app.services.cloudflare.CloudflareClient.delete_dns_record", fake_delete_dns_record)

    headers = _login(client)

    allowed = client.delete("/api/v1/dns/zones/zone-writer/records/rec-1", headers=headers)
    assert allowed.status_code == 200

    denied = client.delete("/api/v1/dns/zones/zone-foreign/records/rec-1", headers=headers)
    assert denied.status_code == 403

    assert deleted == [("zone-writer", "rec-1")]


def test_create_env_is_tenant_scoped(client, monkeypatch):
    asyncio.run(_seed_writer_tenant())

    created: list[tuple[str, str]] = []

    async def fake_create_env(self, application_uuid, key, value, is_preview=False, is_build_time=False):
        created.append((application_uuid, key))
        return {"ok": True}

    monkeypatch.setattr("app.services.coolify.CoolifyClient.create_env", fake_create_env)

    headers = _login(client)
    body = {"key": "API_KEY", "value": "secret"}

    allowed = client.post("/api/v1/sites/app-writer/envs", headers=headers, json=body)
    assert allowed.status_code == 200

    denied = client.post("/api/v1/sites/app-foreign/envs", headers=headers, json=body)
    assert denied.status_code == 403

    assert created == [("app-writer", "API_KEY")]


def test_delete_env_is_tenant_scoped(client, monkeypatch):
    asyncio.run(_seed_writer_tenant())

    deleted: list[tuple[str, str]] = []

    async def fake_delete_env(self, application_uuid, env_uuid):
        deleted.append((application_uuid, env_uuid))
        return {"ok": True}

    monkeypatch.setattr("app.services.coolify.CoolifyClient.delete_env", fake_delete_env)

    headers = _login(client)

    allowed = client.delete("/api/v1/sites/app-writer/envs/env-1", headers=headers)
    assert allowed.status_code == 200

    denied = client.delete("/api/v1/sites/app-foreign/envs/env-1", headers=headers)
    assert denied.status_code == 403

    assert deleted == [("app-writer", "env-1")]
