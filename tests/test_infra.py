"""Hetzner own-infra: client normalization + platform-admin-gated API."""

import asyncio
import json

import httpx

from app.cache import TTLCache
from app.config import get_settings
from app.db import session_scope
from app.models import AdminUser, Plan, Tenant
from app.models.admin import ROLE_OWNER, ROLE_PLATFORM_ADMIN
from app.modules.auth.service import AuthService
from app.services.hetzner import DEFAULT_CLOUD_INIT, HetznerClient, HetznerServer

_SERVER_ITEM = {
    "id": 42, "name": "worker-1", "status": "running", "created": "2026-07-02T10:00:00+00:00",
    "server_type": {"name": "cx23"},
    "public_net": {"ipv4": {"ip": "203.0.113.5"}},
    "datacenter": {"location": {"name": "fsn1"}},
}


def _client(handler) -> HetznerClient:
    return HetznerClient(
        api_token="tok",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        cache=TTLCache(),
    )


# ── Client ─────────────────────────────────────────────────────────────────


def test_list_servers_normalizes():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/servers"
        assert request.headers["Authorization"] == "Bearer tok"
        return httpx.Response(200, json={"servers": [_SERVER_ITEM]})

    [server] = asyncio.run(_client(handler).list_servers())
    assert server == HetznerServer(
        id=42, name="worker-1", status="running", server_type="cx23",
        ipv4="203.0.113.5", location="fsn1", created="2026-07-02T10:00:00+00:00",
    )


def test_create_server_posts_bootstrap_user_data():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST" and request.url.path == "/v1/servers"
        body = json.loads(request.content)
        assert body["name"] == "worker-1" and body["server_type"] == "cx23"
        assert "get.docker.com" in body["user_data"]
        return httpx.Response(
            201,
            json={"server": _SERVER_ITEM, "action": {"id": 7, "status": "running"},
                  "root_password": "pw-once"},
        )

    result = asyncio.run(
        _client(handler).create_server(
            name="worker-1", server_type="cx23", image="ubuntu-24.04",
            user_data=DEFAULT_CLOUD_INIT,
        )
    )
    assert result["root_password"] == "pw-once"


def test_unconfigured_client_lists_nothing():
    client = HetznerClient(api_token="", http_client=None, cache=TTLCache())
    assert asyncio.run(client.list_servers()) == []


# ── API gating ─────────────────────────────────────────────────────────────


async def _seed(*, slug: str, email: str, role: str) -> None:
    async with session_scope() as session:
        auth = AuthService(session)
        plan = Plan(key=f"plan_{slug}", name="P", max_apps=10)
        session.add(plan)
        await session.flush()
        tenant = Tenant(name=slug, slug=slug, status="active", plan_id=plan.id)
        session.add(tenant)
        await session.flush()
        session.add(
            AdminUser(
                tenant_id=tenant.id, email=email, full_name="A", role=role,
                password_hash=auth.hash_password("infra-pass"), is_active=True,
            )
        )


def _login(client, email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "infra-pass"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_owner_cannot_touch_infra(client):
    asyncio.run(_seed(slug="io", email="o@io.test", role=ROLE_OWNER))
    headers = _login(client, "o@io.test")
    assert client.get("/api/v1/infra/servers", headers=headers).status_code == 403
    assert client.post("/api/v1/infra/servers", headers=headers, json={"name": "x"}).status_code == 403
    assert client.delete("/api/v1/infra/servers/1", headers=headers).status_code == 403


def test_platform_admin_unconfigured_and_disabled_paths(client, monkeypatch):
    asyncio.run(_seed(slug="ip", email="p@ip.test", role=ROLE_PLATFORM_ADMIN))
    headers = _login(client, "p@ip.test")
    # No token configured → empty list; provisioning blocked by the actions gate first.
    assert client.get("/api/v1/infra/servers", headers=headers).json() == []
    assert client.post("/api/v1/infra/servers", headers=headers, json={"name": "w"}).status_code == 403
    # Actions on, still unconfigured → 503.
    monkeypatch.setattr(get_settings(), "enable_provider_actions", True)
    assert client.post("/api/v1/infra/servers", headers=headers, json={"name": "w"}).status_code == 503


def test_platform_admin_provisions_with_defaults(client, monkeypatch):
    asyncio.run(_seed(slug="iq", email="q@iq.test", role=ROLE_PLATFORM_ADMIN))
    headers = _login(client, "q@iq.test")
    monkeypatch.setattr(get_settings(), "enable_provider_actions", True)
    monkeypatch.setattr(get_settings(), "hetzner_api_token", "tok")

    captured: dict = {}

    async def fake_create(self, **kwargs):
        captured.update(kwargs)
        return {"server": _SERVER_ITEM, "action": {"id": 7, "status": "running"}, "root_password": "pw"}

    async def fake_wait(self, action_id, **_):
        return "success"

    monkeypatch.setattr(HetznerClient, "create_server", fake_create)
    monkeypatch.setattr(HetznerClient, "wait_action", fake_wait)

    r = client.post("/api/v1/infra/servers", headers=headers, json={"name": "worker-1"})
    assert r.status_code == 200
    body = r.json()
    assert body["server"]["ipv4"] == "203.0.113.5"
    assert body["action_status"] == "success"
    assert body["root_password"] == "pw"
    # platform defaults filled in + bootstrap attached
    assert captured["server_type"] == get_settings().hetzner_server_type
    assert "get.docker.com" in captured["user_data"]
    assert captured["labels"] == {"managed-by": "tetra"}
