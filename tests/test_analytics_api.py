"""Umami analytics client + per-app analytics endpoint (engine apps)."""

import asyncio
import json

import httpx

from app.cache import TTLCache
from app.modules.analytics.service import _num, _series, _summary, _valid_domain
from app.services.umami import UmamiClient


def _login_as(client, email: str, password: str) -> dict[str, str]:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['token']}"}


def _umami(handler) -> UmamiClient:
    return UmamiClient(
        base_url="https://umami.test",
        username="u",
        password="p",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        cache=TTLCache(),
    )


# ── client ──────────────────────────────────────────────────────────────

def test_umami_logs_in_then_calls_stats_with_bearer():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/auth/login":
            seen["login"] = True
            assert json.loads(request.content) == {"username": "u", "password": "p"}
            return httpx.Response(200, json={"token": "tok-123"})
        assert request.url.path == "/api/websites/w1/stats"
        assert request.headers["Authorization"] == "Bearer tok-123"
        assert request.url.params.get("startAt") == "1000"
        return httpx.Response(
            200,
            json={"pageviews": 10, "visitors": 4, "visits": 5, "bounces": 2, "totaltime": 100},
        )

    stats = asyncio.run(_umami(handler).get_stats("w1", 1000, 2000))
    assert seen.get("login") is True
    assert stats["pageviews"] == 10


def test_umami_find_or_create_matches_existing_domain_case_insensitive():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/auth/login":
            return httpx.Response(200, json={"token": "t"})
        if request.url.path == "/api/websites" and request.method == "GET":
            return httpx.Response(200, json={"data": [{"id": "w9", "domain": "Shop.Example.com"}]})
        raise AssertionError(f"unexpected {request.method} {request.url.path}")

    site = asyncio.run(_umami(handler).find_or_create_website(domain="shop.example.com", name="Shop"))
    assert site["id"] == "w9"


def test_umami_find_or_create_creates_when_missing():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/auth/login":
            return httpx.Response(200, json={"token": "t"})
        if request.url.path == "/api/websites" and request.method == "GET":
            return httpx.Response(200, json={"data": []})
        if request.url.path == "/api/websites" and request.method == "POST":
            assert json.loads(request.content) == {"name": "Shop", "domain": "shop.example.com"}
            return httpx.Response(200, json={"id": "new1", "domain": "shop.example.com"})
        raise AssertionError(f"unexpected {request.method} {request.url.path}")

    site = asyncio.run(_umami(handler).find_or_create_website(domain="shop.example.com", name="Shop"))
    assert site["id"] == "new1"


# ── pure helpers ────────────────────────────────────────────────────────

def test_analytics_helpers():
    summary = _summary(
        {"pageviews": 100, "visitors": 40, "visits": 50, "bounces": 25, "totaltime": 500}
    )
    assert summary["pageviews"] == 100
    assert summary["bounce_rate"] == 50  # 25/50
    assert summary["avg_seconds"] == 10  # 500/50

    assert _num({"value": 7}) == 7 and _num(3) == 3 and _num(None) == 0

    series = _series(
        {"pageviews": [{"x": "2026-06-30", "y": 5}], "sessions": [{"x": "2026-06-30", "y": 2}]}
    )
    assert series == [{"date": "2026-06-30", "pageviews": 5, "sessions": 2}]

    # Non-hostnames are rejected.
    assert _valid_domain("shop.example.com") is True
    assert _valid_domain("") is False
    assert _valid_domain("localhost") is False  # no dot


# ── endpoint ────────────────────────────────────────────────────────────


def _seed_engine_app(project: str = "app-x") -> None:
    """Give the bootstrap admin's tenant an engine app (TenantResource docker/app)."""
    import asyncio as _asyncio

    from sqlalchemy import select

    from app.db import session_scope
    from app.models import AdminUser, TenantResource
    from app.models.tenant_resource import PROVIDER_DOCKER, RESOURCE_TYPE_APP

    async def go() -> None:
        async with session_scope() as session:
            admin = await session.scalar(select(AdminUser).where(AdminUser.email == "admin@example.com"))
            session.add(TenantResource(
                tenant_id=admin.tenant_id, provider=PROVIDER_DOCKER, resource_type=RESOURCE_TYPE_APP,
                external_id=project, display_name=project,
            ))

    _asyncio.run(go())


def test_app_analytics_requires_auth(client):
    assert client.get("/api/v1/apps/app-x/analytics").status_code == 401


def test_app_analytics_not_configured(client):
    """With Umami unset (test env), an accessible engine app returns configured=false."""
    _seed_engine_app()
    headers = _login_as(client, "admin@example.com", "supersecurepassword")
    resp = client.get("/api/v1/apps/app-x/analytics", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["configured"] is False
    assert body["ready"] is False


def test_app_analytics_unknown_app_is_404(client):
    headers = _login_as(client, "admin@example.com", "supersecurepassword")
    assert client.get("/api/v1/apps/nope/analytics", headers=headers).status_code == 404
