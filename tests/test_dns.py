"""DNS read surface: tenant-scoped zone/record listing + graceful provider degradation.

Write paths (create/update/delete records) are covered in test_write_actions.py.
"""

import asyncio

from app.db import session_scope
from app.models import AdminUser, Tenant, TenantResource
from app.models.tenant_resource import PROVIDER_CLOUDFLARE, RESOURCE_TYPE_DNS_ZONE
from app.modules.auth.service import AuthService
from app.services.cloudflare import CloudflareDNSRecord, CloudflareZone
from app.services.http import ProviderAPIError

ZONES = [
    CloudflareZone(id="zone-a", name="a.test", status="active"),
    CloudflareZone(id="zone-b", name="b.test", status="active"),
]

RECORDS = {
    "zone-a": [
        CloudflareDNSRecord(id="rec-1", type="A", name="a.test", content="1.2.3.4", ttl=1),
    ],
    "zone-b": [
        CloudflareDNSRecord(id="rec-2", type="A", name="b.test", content="5.6.7.8", ttl=1),
    ],
}


async def _seed_dns_tenant() -> None:
    async with session_scope() as session:
        auth_service = AuthService(session)
        tenant = Tenant(name="Zone Tenant", slug="zonetenant", status="active")
        session.add(tenant)
        await session.flush()
        session.add(
            AdminUser(
                tenant_id=tenant.id,
                email="owner@zonetenant.test",
                full_name="Zone Owner",
                password_hash=auth_service.hash_password("zone-password"),
                is_active=True,
            )
        )
        session.add(
            TenantResource(
                tenant_id=tenant.id,
                provider=PROVIDER_CLOUDFLARE,
                resource_type=RESOURCE_TYPE_DNS_ZONE,
                external_id="zone-a",
                display_name="a.test",
            )
        )


def _login(client, email: str = "owner@zonetenant.test", password: str = "zone-password"):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def _mock_cloudflare(monkeypatch) -> None:
    async def fake_list_zones(self, refresh=False):
        return ZONES

    async def fake_list_dns_records(self, zone_id, refresh=False):
        return RECORDS.get(zone_id, [])

    monkeypatch.setattr(
        "app.services.cloudflare.CloudflareClient.list_zones", fake_list_zones
    )
    monkeypatch.setattr(
        "app.services.cloudflare.CloudflareClient.list_dns_records", fake_list_dns_records
    )
    monkeypatch.setattr(
        "app.services.cloudflare.CloudflareClient.is_configured", lambda self: True
    )


def test_dns_listing_is_tenant_scoped(client, monkeypatch):
    asyncio.run(_seed_dns_tenant())
    _mock_cloudflare(monkeypatch)

    response = client.get("/api/v1/dns", headers=_login(client))
    assert response.status_code == 200
    payload = response.json()

    zone_ids = [zone["id"] for zone in payload["zones"]]
    assert zone_ids == ["zone-a"]
    assert payload["selected_zone"] == "zone-a"
    assert [record["id"] for record in payload["records"]] == ["rec-1"]
    assert payload["providers"][0]["name"] == "Cloudflare"


def test_dns_denies_foreign_zone_selection(client, monkeypatch):
    asyncio.run(_seed_dns_tenant())
    _mock_cloudflare(monkeypatch)

    response = client.get("/api/v1/dns", params={"zone": "zone-b"}, headers=_login(client))
    assert response.status_code == 200
    payload = response.json()
    # The foreign zone must not leak records to this tenant.
    assert all(zone["id"] != "zone-b" for zone in payload["zones"])
    assert all(record["id"] != "rec-2" for record in payload["records"])


def test_dns_platform_admin_sees_all_zones(client, monkeypatch):
    _mock_cloudflare(monkeypatch)

    headers = _login(client, email="admin@example.com", password="supersecurepassword")
    response = client.get("/api/v1/dns", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert [zone["id"] for zone in payload["zones"]] == ["zone-a", "zone-b"]


def test_dns_degrades_gracefully_when_provider_down(client, monkeypatch):
    asyncio.run(_seed_dns_tenant())

    async def failing_list_zones(self, refresh=False):
        raise ProviderAPIError(service="cloudflare", message="upstream 502", status_code=502)

    monkeypatch.setattr(
        "app.services.cloudflare.CloudflareClient.list_zones", failing_list_zones
    )

    response = client.get("/api/v1/dns", headers=_login(client))
    assert response.status_code == 200
    payload = response.json()
    assert payload["zones"] == []
    assert payload["providers"][0]["status"] == "degraded"
