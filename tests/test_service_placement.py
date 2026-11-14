"""ADR 0019: services are created *into* an environment, and stack names are global."""

import asyncio
import base64

from sqlalchemy import select

from app.db import session_scope
from app.models import Deployment, WorkspaceApp
from app.services.app_catalog import AppTemplate
from app.services.builder import BuildError
from tests.test_databases import _headers, _seed, engine_fakes  # noqa: F401  (fixture)


def _production_env(client, headers, team: str, project: str) -> str:
    created = client.post(f"/api/v1/teams/{team}/projects", json={"name": project}, headers=headers)
    assert created.status_code == 201, created.text
    envs = client.get(
        f"/api/v1/teams/{team}/projects/{project}/environments", headers=headers
    ).json()
    return next(e["id"] for e in envs if e["slug"] == "production")


def _services(client, headers, team: str, **params) -> dict[str, dict]:
    resp = client.get(f"/api/v1/teams/{team}/apps", headers=headers, params=params)
    assert resp.status_code == 200, resp.text
    return {a["name"]: a for a in resp.json()}


def _fake_template(monkeypatch):
    compose_b64 = base64.b64encode(b"services:\n  web:\n    image: nginx\n").decode()

    async def get_template(self, slug):
        return AppTemplate(slug=slug, name="Ghost", compose_b64=compose_b64)

    monkeypatch.setattr("app.services.app_catalog.AppCatalog.get_template", get_template)


def test_database_is_created_into_an_environment(client, engine_fakes):  # noqa: F811
    asyncio.run(_seed("acme"))
    h = _headers(client, "acme")
    env_id = _production_env(client, h, "acme", "demo")

    r = client.post(
        "/api/v1/databases",
        json={"name": "shop-db", "engine": "postgres", "environment_id": env_id},
        headers=h,
    )
    assert r.status_code == 201, r.text

    services = _services(client, h, "acme", project="demo", environment="production")
    db = services["shop-db"]
    assert (db["kind"], db["database_id"], db["environment"]["id"]) == ("database", r.json()["id"], env_id)
    assert db["external_id"].startswith("tdb-")


def test_database_without_environment_goes_to_the_databases_project(client, engine_fakes):  # noqa: F811
    asyncio.run(_seed("acme"))
    h = _headers(client, "acme")
    r = client.post("/api/v1/databases", json={"name": "cache", "engine": "redis"}, headers=h)
    assert r.status_code == 201, r.text

    row = _services(client, h, "acme")["cache"]
    assert (row["kind"], row["project"]["slug"], row["environment"]["slug"]) == (
        "database", "databases", "production",
    )

    # Deleting the database drops its service row.
    assert client.delete(f"/api/v1/databases/{r.json()['id']}", headers=h).status_code in (200, 204)
    assert "cache" not in _services(client, h, "acme")


def test_another_teams_environment_is_refused(client, engine_fakes, monkeypatch):  # noqa: F811
    asyncio.run(_seed("acme"))
    asyncio.run(_seed("beta"))
    foreign_env = _production_env(client, _headers(client, "beta"), "beta", "theirs")
    h = _headers(client, "acme")

    r = client.post(
        "/api/v1/databases",
        json={"name": "sneaky", "engine": "postgres", "environment_id": foreign_env},
        headers=h,
    )
    assert r.status_code == 404, r.text

    _fake_template(monkeypatch)
    r = client.post(
        "/api/v1/apps/install",
        json={"slug": "ghost", "name": "sneaky-app", "environment_id": foreign_env},
        headers=h,
    )
    assert r.status_code == 404, r.text
    assert engine_fakes["deployed"] == {}


def test_template_install_is_placed(client, engine_fakes, monkeypatch):  # noqa: F811
    asyncio.run(_seed("acme"))
    h = _headers(client, "acme")
    env_id = _production_env(client, h, "acme", "site")
    _fake_template(monkeypatch)

    r = client.post(
        "/api/v1/apps/install",
        json={"slug": "ghost", "name": "acme-blog", "environment_id": env_id},
        headers=h,
    )
    assert r.status_code == 200, r.text
    row = _services(client, h, "acme", project="site")["acme-blog"]
    assert (row["kind"], row["environment"]["id"], row["database_id"]) == ("app", env_id, None)


def test_git_deploy_is_placed_before_the_build(client, engine_fakes, monkeypatch):  # noqa: F811
    asyncio.run(_seed("acme"))
    h = _headers(client, "acme")
    env_id = _production_env(client, h, "acme", "api")

    async def build(self, git_url, ref, *, project, on_line=None):
        raise BuildError(message="no network in tests")

    monkeypatch.setattr("app.services.builder.Builder.build_from_git", build)
    r = client.post(
        "/api/v1/deploys/git",
        json={"git_url": "https://github.com/x/y.git", "name": "acme-api", "environment_id": env_id},
        headers=h,
    )
    assert r.status_code == 200, r.text

    async def placed():
        async with session_scope() as session:
            row = await session.scalar(select(WorkspaceApp).where(WorkspaceApp.external_id == "acme-api"))
            return row.environment_id, row.kind

    assert asyncio.run(placed()) == (env_id, "app")
    # The failed build keeps its deployment row, so the service stays in its environment.
    assert "acme-api" in _services(client, h, "acme", project="api")

    async def deployment_rows():
        async with session_scope() as session:
            return len((await session.scalars(
                select(Deployment).where(Deployment.project == "acme-api")
            )).all())

    assert asyncio.run(deployment_rows()) == 1


def test_stack_names_are_unique_across_tenants(client, engine_fakes, monkeypatch):  # noqa: F811
    asyncio.run(_seed("acme"))
    asyncio.run(_seed("beta", app="shared"))
    _fake_template(monkeypatch)
    h = _headers(client, "acme")

    r = client.post("/api/v1/apps/install", json={"slug": "ghost", "name": "shared"}, headers=h)
    assert r.status_code == 409, r.text
    assert "taken" in r.json()["detail"] and "beta" not in r.json()["detail"]

    r = client.post(
        "/api/v1/deploys/git",
        json={"git_url": "https://github.com/x/y.git", "name": "shared"},
        headers=h,
    )
    assert r.status_code == 409, r.text
    assert engine_fakes["deployed"] == {}
