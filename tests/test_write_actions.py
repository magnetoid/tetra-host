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
        tenant = Tenant(name="Writer Tenant", slug="writer", status="active")
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


def test_update_dns_record_is_tenant_scoped(client, monkeypatch):
    asyncio.run(_seed_writer_tenant())

    updated: list[tuple[str, str, str]] = []

    async def fake_update_dns_record(
        self, zone_id, record_id, record_type, name, content, ttl=1, proxied=False, priority=None
    ):
        updated.append((zone_id, record_id, record_type))
        return {"ok": True}

    monkeypatch.setattr("app.services.cloudflare.CloudflareClient.update_dns_record", fake_update_dns_record)

    headers = _login(client)
    body = {"type": "A", "name": "app.writer.test", "content": "5.6.7.8", "ttl": 1, "proxied": False}

    allowed = client.put("/api/v1/dns/zones/zone-writer/records/rec-1", headers=headers, json=body)
    assert allowed.status_code == 200
    assert allowed.json()["message"] == "DNS record updated."

    denied = client.put("/api/v1/dns/zones/zone-foreign/records/rec-1", headers=headers, json=body)
    assert denied.status_code == 403

    assert updated == [("zone-writer", "rec-1", "A")]


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


def test_zone_settings_and_purge_are_tenant_scoped(client, monkeypatch):
    asyncio.run(_seed_writer_tenant())

    async def fake_get_zone_settings(self, zone_id):
        return {
            "ssl": "full",
            "always_use_https": "on",
            "development_mode": "off",
            "security_level": "medium",
            "dnssec": "active",
        }

    async def fake_update_zone_setting(self, zone_id, setting, value):
        return {"ok": True}

    async def fake_purge_cache(self, zone_id, everything=True, files=None):
        return {"ok": True}

    monkeypatch.setattr("app.services.cloudflare.CloudflareClient.get_zone_settings", fake_get_zone_settings)
    monkeypatch.setattr("app.services.cloudflare.CloudflareClient.update_zone_setting", fake_update_zone_setting)
    monkeypatch.setattr("app.services.cloudflare.CloudflareClient.purge_cache", fake_purge_cache)

    headers = _login(client)

    settings = client.get("/api/v1/dns/zones/zone-writer/settings", headers=headers)
    assert settings.status_code == 200
    assert settings.json()["ssl"] == "full"
    assert settings.json()["dnssec"] == "active"
    assert client.get("/api/v1/dns/zones/zone-foreign/settings", headers=headers).status_code == 403

    patched = client.patch(
        "/api/v1/dns/zones/zone-writer/settings", headers=headers, json={"setting": "ssl", "value": "strict"}
    )
    assert patched.status_code == 200
    assert client.patch(
        "/api/v1/dns/zones/zone-foreign/settings", headers=headers, json={"setting": "ssl", "value": "strict"}
    ).status_code == 403

    purged = client.post("/api/v1/dns/zones/zone-writer/purge", headers=headers, json={"everything": True})
    assert purged.status_code == 200
    assert client.post(
        "/api/v1/dns/zones/zone-foreign/purge", headers=headers, json={"everything": True}
    ).status_code == 403


def test_zone_analytics_is_tenant_scoped(client, monkeypatch):
    asyncio.run(_seed_writer_tenant())

    captured: list[tuple[str, int]] = []

    async def fake_get_zone_analytics(self, zone_id, days=7):
        captured.append((zone_id, days))
        return {
            "since": "2026-06-21",
            "until": "2026-06-28",
            "points": [
                {"date": "2026-06-27", "requests": 100, "bytes": 2048,
                 "cached_requests": 60, "threats": 1, "uniques": 25},
            ],
            "totals": {"requests": 100, "bytes": 2048, "cached_requests": 60, "threats": 1, "uniques": 25},
        }

    monkeypatch.setattr(
        "app.services.cloudflare.CloudflareClient.get_zone_analytics", fake_get_zone_analytics
    )

    headers = _login(client)

    allowed = client.get("/api/v1/dns/zones/zone-writer/analytics?days=7", headers=headers)
    assert allowed.status_code == 200
    body = allowed.json()
    assert body["zone_id"] == "zone-writer"
    assert body["totals"]["requests"] == 100
    assert body["points"][0]["uniques"] == 25

    denied = client.get("/api/v1/dns/zones/zone-foreign/analytics", headers=headers)
    assert denied.status_code == 403

    assert captured == [("zone-writer", 7)]


def test_dns_export_is_tenant_scoped(client, monkeypatch):
    asyncio.run(_seed_writer_tenant())

    bind = ";; Domain: writer.test\n$ORIGIN writer.test.\nwww 1 IN A 1.2.3.4\nmail 1 IN A 5.6.7.8\n"

    async def fake_export(self, zone_id):
        return bind

    monkeypatch.setattr("app.services.cloudflare.CloudflareClient.export_dns_records", fake_export)

    headers = _login(client)

    allowed = client.get("/api/v1/dns/zones/zone-writer/export", headers=headers)
    assert allowed.status_code == 200
    payload = allowed.json()
    assert payload["bind"] == bind
    assert payload["record_count"] == 2  # comments and $ORIGIN excluded

    denied = client.get("/api/v1/dns/zones/zone-foreign/export", headers=headers)
    assert denied.status_code == 403


def test_dns_import_is_tenant_scoped(client, monkeypatch):
    asyncio.run(_seed_writer_tenant())

    imported: list[tuple[str, str]] = []

    async def fake_import(self, zone_id, bind_text):
        imported.append((zone_id, bind_text))
        return {"result": {"recs_added": 3, "total_records_parsed": 3}}

    monkeypatch.setattr("app.services.cloudflare.CloudflareClient.import_dns_records", fake_import)

    headers = _login(client)
    body = {"bind": "www 1 IN A 1.2.3.4\n"}

    allowed = client.post("/api/v1/dns/zones/zone-writer/import", headers=headers, json=body)
    assert allowed.status_code == 200
    assert allowed.json()["message"] == "Imported 3 records."

    empty = client.post("/api/v1/dns/zones/zone-writer/import", headers=headers, json={"bind": "  "})
    assert empty.status_code == 400

    denied = client.post("/api/v1/dns/zones/zone-foreign/import", headers=headers, json=body)
    assert denied.status_code == 403

    assert imported == [("zone-writer", "www 1 IN A 1.2.3.4\n")]


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
