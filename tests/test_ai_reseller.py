"""AI reselling — OpenRouter per-tenant runtime keys (Path A: direct keys)."""

import asyncio
import json

import httpx

from app.cache import TTLCache
from app.config import get_settings
from app.db import session_scope
from app.models import AdminUser, Plan, Tenant
from app.models.admin import ROLE_OWNER
from app.models.tenant_resource import (
    PROVIDER_OPENROUTER,
    RESOURCE_TYPE_AI_KEY,
    TenantResource,
)
from app.modules.auth.service import AuthService
from app.services.openrouter import OpenRouterClient


def _client(handler) -> OpenRouterClient:
    return OpenRouterClient(
        provisioning_key="mgmt",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        cache=TTLCache(),
    )


# ── Client (real OpenRouter shapes, network-free) ───────────────────────────
def test_create_key_posts_name_and_limit():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST" and request.url.path == "/api/v1/keys"
        assert request.headers["Authorization"] == "Bearer mgmt"
        body = json.loads(request.content)
        assert body == {"name": "acme", "limit": 25.0, "limitReset": "monthly"}
        return httpx.Response(200, json={
            "key": "sk-or-v1-secret", "data": {"hash": "h123", "label": "acme", "limit": 25}})

    result = asyncio.run(_client(handler).create_key("acme", limit=25.0, limit_reset="monthly"))
    assert result["key"] == "sk-or-v1-secret" and result["data"]["hash"] == "h123"


def test_list_models_reads_data_array():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/models"
        return httpx.Response(200, json={"data": [{"id": "openai/gpt-5", "name": "GPT-5"}]})

    models = asyncio.run(_client(handler).list_models())
    assert models[0]["id"] == "openai/gpt-5"


def test_delete_key_hits_hash_path():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        return httpx.Response(200, json={"data": {}})

    asyncio.run(_client(handler).delete_key("h123"))
    assert seen == {"method": "DELETE", "path": "/api/v1/keys/h123"}


# ── API (tenant-scoped, ownership + actions-gated) ──────────────────────────
async def _seed(*, slug: str, email: str) -> None:
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
            password_hash=auth.hash_password("ai-pass"), is_active=True,
        ))


def _login(client, email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "ai-pass"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_provision_key_gated_returns_secret_once_and_records(client, monkeypatch):
    asyncio.run(_seed(slug="ai1", email="a@ai1.test"))
    headers = _login(client, "a@ai1.test")

    # actions disabled → 403
    monkeypatch.setattr(get_settings(), "enable_provider_actions", False)
    monkeypatch.setattr(get_settings(), "openrouter_provisioning_key", "mgmt")
    assert client.post("/api/v1/ai/keys", headers=headers,
                       json={"label": "acme"}).status_code == 403

    # actions on → provisions (client mocked), returns secret once, records resource
    monkeypatch.setattr(get_settings(), "enable_provider_actions", True)

    async def fake_create(self, name, *, limit=None, limit_reset=None):
        return {"key": "sk-or-v1-secret", "data": {"hash": "h999", "label": name, "limit": limit}}

    monkeypatch.setattr(OpenRouterClient, "create_key", fake_create)
    r = client.post("/api/v1/ai/keys", headers=headers, json={"label": "acme", "limit": 25})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["key"] == "sk-or-v1-secret" and body["hash"] == "h999"

    async def _count() -> int:
        from sqlalchemy import func, select
        async with session_scope() as session:
            return await session.scalar(
                select(func.count()).select_from(TenantResource).where(
                    TenantResource.provider == PROVIDER_OPENROUTER,
                    TenantResource.resource_type == RESOURCE_TYPE_AI_KEY,
                )
            ) or 0

    assert asyncio.run(_count()) == 1


def test_update_foreign_key_is_404(client, monkeypatch):
    asyncio.run(_seed(slug="ai2", email="b@ai2.test"))
    headers = _login(client, "b@ai2.test")
    monkeypatch.setattr(get_settings(), "enable_provider_actions", True)
    monkeypatch.setattr(get_settings(), "openrouter_provisioning_key", "mgmt")
    # tenant owns no keys → managing an arbitrary hash 404s (never reaches OpenRouter)
    assert client.patch("/api/v1/ai/keys/hFOREIGN", headers=headers,
                        json={"limit": 5}).status_code == 404
    assert client.delete("/api/v1/ai/keys/hFOREIGN", headers=headers).status_code == 404
