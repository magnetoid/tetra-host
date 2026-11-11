"""GlitchTip error-tracking client + per-project errors endpoint."""

import asyncio

import httpx

from app.cache import TTLCache
from app.modules.errors.service import _issue, _slugify
from app.services.glitchtip import GlitchtipClient


def _login_as(client, email: str, password: str) -> dict[str, str]:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['token']}"}


def _glitchtip(handler) -> GlitchtipClient:
    return GlitchtipClient(
        base_url="https://gt.test",
        token="tok",
        org="acme",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        cache=TTLCache(),
    )


# ── client ──────────────────────────────────────────────────────────────

def test_list_issues_sends_bearer_and_query():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/0/projects/acme/web/issues/"
        assert request.headers["Authorization"] == "Bearer tok"
        assert request.url.params.get("query") == "is:unresolved"
        return httpx.Response(200, json=[{"id": "1", "title": "Boom", "level": "error", "count": 3}])

    issues = asyncio.run(_glitchtip(handler).list_issues("web"))
    assert issues[0]["title"] == "Boom"


def test_find_or_create_project_matches_existing_slug():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/0/organizations/acme/projects/":
            return httpx.Response(200, json=[{"slug": "web", "name": "Web"}])
        raise AssertionError(f"unexpected {request.method} {request.url.path}")

    project = asyncio.run(_glitchtip(handler).find_or_create_project(slug="web", name="Web"))
    assert project and project["slug"] == "web"


def test_find_or_create_project_creates_under_first_team():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/0/organizations/acme/projects/":
            return httpx.Response(200, json=[])
        if request.url.path == "/api/0/organizations/acme/teams/":
            return httpx.Response(200, json=[{"slug": "core"}])
        if request.url.path == "/api/0/teams/acme/core/projects/" and request.method == "POST":
            return httpx.Response(201, json={"slug": "web", "name": "Web"})
        raise AssertionError(f"unexpected {request.method} {request.url.path}")

    project = asyncio.run(_glitchtip(handler).find_or_create_project(slug="web", name="Web"))
    assert project and project["slug"] == "web"


def test_get_project_dsn_extracts_public():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/0/projects/acme/web/keys/"
        return httpx.Response(200, json=[{"dsn": {"public": "https://abc@gt.test/1"}}])

    dsn = asyncio.run(_glitchtip(handler).get_project_dsn("web"))
    assert dsn == "https://abc@gt.test/1"


# ── helpers ─────────────────────────────────────────────────────────────

def test_errors_helpers():
    assert _slugify("My Cool App!") == "my-cool-app"
    assert _slugify("") == "project"
    norm = _issue({"id": "9", "title": "X", "level": "warning", "count": 5, "userCount": 2})
    assert norm["id"] == "9" and norm["level"] == "warning" and norm["count"] == 5
    assert norm["user_count"] == 2


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


def test_app_errors_requires_auth(client):
    assert client.get("/api/v1/apps/app-x/errors").status_code == 401


def test_app_errors_not_configured(client):
    _seed_engine_app()
    headers = _login_as(client, "admin@example.com", "supersecurepassword")
    resp = client.get("/api/v1/apps/app-x/errors", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["configured"] is False and body["ready"] is False


def test_app_errors_unknown_app_is_404(client):
    headers = _login_as(client, "admin@example.com", "supersecurepassword")
    assert client.get("/api/v1/apps/nope/errors", headers=headers).status_code == 404
