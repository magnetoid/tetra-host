"""Reseller — Cloudflare plans + services on tenant zones (Path A)."""

import asyncio
import json

import httpx

from app.cache import TTLCache
from app.config import get_settings
from app.db import session_scope
from app.models import AdminUser, Plan, Tenant
from app.models.admin import ROLE_OWNER
from app.models.tenant_resource import (
    PROVIDER_CLOUDFLARE,
    RESOURCE_TYPE_CLOUDFLARE_SERVICE,
    RESOURCE_TYPE_DNS_ZONE,
    TenantResource,
)
from app.modules.auth.service import AuthService
from app.services.cloudflare import CloudflareClient

CF = "https://api.cloudflare.com/client/v4"


def _client(handler) -> CloudflareClient:
    return CloudflareClient(
        api_token="tok",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        cache=TTLCache(),
    )


# ── Client (real Cloudflare API shapes, network-free) ───────────────────────
def test_list_available_plans():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/client/v4/zones/z1/available_plans"
        return httpx.Response(200, json={"success": True, "result": [
            {"id": "pro", "name": "Pro", "price": 20, "currency": "USD",
             "frequency": "monthly", "can_subscribe": True, "is_subscribed": False},
        ]})

    plans = asyncio.run(_client(handler).list_available_plans("z1"))
    assert plans[0]["id"] == "pro"


def test_set_zone_subscription_posts_rate_plan():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/client/v4/zones/z1/subscription"
        body = json.loads(request.content)
        assert body == {"frequency": "monthly", "rate_plan": {"id": "business"}}
        return httpx.Response(200, json={"success": True, "result": {
            "id": "sub1", "state": "Paid", "price": 200, "currency": "USD",
            "frequency": "monthly", "rate_plan": {"id": "business"}}})

    result = asyncio.run(_client(handler).set_zone_subscription("z1", "business"))
    assert result["state"] == "Paid" and result["rate_plan"]["id"] == "business"


def test_set_argo_smart_routing_patches_value():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PATCH"
        assert request.url.path == "/client/v4/zones/z1/argo/smart_routing"
        assert json.loads(request.content) == {"value": "on"}
        return httpx.Response(200, json={"success": True, "result": {"value": "on"}})

    assert asyncio.run(_client(handler).set_argo_smart_routing("z1", True))["value"] == "on"


# ── API (tenant-scoped, ownership + actions-gated) ──────────────────────────
async def _seed(*, slug: str, email: str, own_zone: str | None = None) -> None:
    async with session_scope() as session:
        auth = AuthService(session)
        plan = Plan(key=f"plan_{slug}", name="P", max_apps=10)
        session.add(plan)
        await session.flush()
        tenant = Tenant(name=slug, slug=slug, status="active", plan_id=plan.id, is_platform_scope=False)
        session.add(tenant)
        await session.flush()
        session.add(AdminUser(
            tenant_id=tenant.id, email=email, full_name="A", role=ROLE_OWNER,
            password_hash=auth.hash_password("resell-pass"), is_active=True,
        ))
        if own_zone:
            session.add(TenantResource(
                tenant_id=tenant.id, provider=PROVIDER_CLOUDFLARE,
                resource_type=RESOURCE_TYPE_DNS_ZONE, external_id=own_zone, display_name="z",
            ))


def _login(client, email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "resell-pass"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_catalog_lists_services(client):
    asyncio.run(_seed(slug="rc", email="c@rc.test"))
    headers = _login(client, "c@rc.test")
    rows = client.get("/api/v1/cloudflare/services", headers=headers).json()
    keys = {r["key"] for r in rows}
    assert {"plan_pro", "argo", "waf_managed", "r2"} <= keys
    assert any(r["category"] == "performance" for r in rows)


def test_zone_not_owned_is_404(client):
    asyncio.run(_seed(slug="rd", email="d@rd.test"))  # owns no zone
    headers = _login(client, "d@rd.test")
    assert client.get("/api/v1/cloudflare/zones/zX/plans", headers=headers).status_code == 404


def test_activate_plan_gated_then_records(client, monkeypatch):
    asyncio.run(_seed(slug="re", email="e@re.test", own_zone="zOwned"))
    headers = _login(client, "e@re.test")

    # actions disabled → 403 even for an owned zone
    monkeypatch.setattr(get_settings(), "enable_provider_actions", False)
    monkeypatch.setattr(get_settings(), "cloudflare_api_token", "tok")
    blocked = client.post(
        "/api/v1/cloudflare/zones/zOwned/subscription", headers=headers,
        json={"rate_plan_id": "pro"},
    )
    assert blocked.status_code == 403

    # actions on → activates (client mocked), records a TenantResource
    monkeypatch.setattr(get_settings(), "enable_provider_actions", True)

    async def fake_get_sub(self, zone_id):
        return {}

    async def fake_set_sub(self, zone_id, rate_plan_id, *, frequency="monthly", update=False):
        assert zone_id == "zOwned" and rate_plan_id == "pro" and update is False
        return {"id": "sub1", "state": "Paid", "rate_plan": {"id": "pro"}}

    monkeypatch.setattr(CloudflareClient, "get_zone_subscription", fake_get_sub)
    monkeypatch.setattr(CloudflareClient, "set_zone_subscription", fake_set_sub)

    ok = client.post(
        "/api/v1/cloudflare/zones/zOwned/subscription", headers=headers,
        json={"rate_plan_id": "pro"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["rate_plan_id"] == "pro" and ok.json()["state"] == "Paid"

    async def _count() -> int:
        from sqlalchemy import func, select
        async with session_scope() as session:
            return await session.scalar(
                select(func.count()).select_from(TenantResource).where(
                    TenantResource.resource_type == RESOURCE_TYPE_CLOUDFLARE_SERVICE
                )
            ) or 0

    assert asyncio.run(_count()) == 1


def test_activate_argo_service(client, monkeypatch):
    asyncio.run(_seed(slug="rf", email="f@rf.test", own_zone="zArgo"))
    headers = _login(client, "f@rf.test")
    monkeypatch.setattr(get_settings(), "enable_provider_actions", True)
    monkeypatch.setattr(get_settings(), "cloudflare_api_token", "tok")

    async def fake_argo(self, zone_id, enabled):
        assert zone_id == "zArgo" and enabled is True
        return {"value": "on"}

    monkeypatch.setattr(CloudflareClient, "set_argo_smart_routing", fake_argo)
    r = client.post("/api/v1/cloudflare/zones/zArgo/services/argo/activate", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["service"] == "argo" and "Argo" in r.json()["note"]
