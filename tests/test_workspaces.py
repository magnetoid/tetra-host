"""Team → project → environment → app hierarchy: indexing, placement and team isolation."""

import asyncio
import os

import pytest
from sqlalchemy import delete, select

from app.db import session_scope
from app.models import (
    AdminUser,
    Deployment,
    PreviewEnv,
    Tenant,
    TenantResource,
    WorkspaceApp,
)
from app.models.admin import ROLE_OWNER
from app.models.team import ROLE_MEMBER
from app.models.tenant_resource import PROVIDER_DOCKER, RESOURCE_TYPE_APP
from app.modules.auth.service import AuthService

PASSWORD = "tenant-password"


def _engine_app(tenant_id: str, project: str) -> TenantResource:
    return TenantResource(
        tenant_id=tenant_id, provider=PROVIDER_DOCKER, resource_type=RESOURCE_TYPE_APP,
        external_id=project, display_name=project,
    )


async def _seed() -> None:
    async with session_scope() as session:
        auth = AuthService(session)
        for slug, role in (("alpha", ROLE_OWNER), ("beta", ROLE_OWNER)):
            tenant = Tenant(name=slug.title(), slug=slug, status="active")
            session.add(tenant)
            await session.flush()
            session.add(AdminUser(
                tenant_id=tenant.id, email=f"{slug}@x.test", full_name=slug,
                password_hash=auth.hash_password(PASSWORD), is_active=True, role=role,
            ))
            if slug == "alpha":
                session.add(AdminUser(
                    tenant_id=tenant.id, email="alpha-member@x.test", full_name="m",
                    password_hash=auth.hash_password(PASSWORD), is_active=True, role=ROLE_MEMBER,
                ))
                # A git deploy, its preview, and a marketplace install with no deployment row.
                session.add(_engine_app(tenant.id, "shop"))
                session.add(Deployment(tenant_id=tenant.id, project="shop", domain="shop.test", status="ready"))
                session.add(Deployment(tenant_id=tenant.id, project="shop-pr-x", domain="x.shop.test"))
                session.add(PreviewEnv(
                    tenant_id=tenant.id, project="shop", branch="feature/x",
                    preview_project="shop-pr-x", domain="x.shop.test",
                ))
                session.add(_engine_app(tenant.id, "wiki"))
            else:
                session.add(_engine_app(tenant.id, "blog"))
                session.add(Deployment(tenant_id=tenant.id, project="blog", domain="blog.test"))
        platform = await session.scalar(select(Tenant).where(Tenant.is_platform_scope.is_(True)))
        session.add(_engine_app(platform.id, "platform-app"))


def _login(client, email: str, password: str = PASSWORD) -> dict[str, str]:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['token']}"}


def _root(client) -> dict[str, str]:
    return _login(client, os.environ["ADMIN_BOOTSTRAP_EMAIL"], os.environ["ADMIN_BOOTSTRAP_PASSWORD"])


@pytest.fixture
def seeded(client):
    asyncio.run(_seed())
    return client


def _apps(client, headers, team: str, **params) -> dict[str, dict]:
    resp = client.get(f"/api/v1/teams/{team}/apps", headers=headers, params=params)
    assert resp.status_code == 200, resp.text
    return {a["name"]: a for a in resp.json()}


def test_team_sees_only_its_hierarchy(seeded):
    alpha = _login(seeded, "alpha@x.test")

    assert [t["slug"] for t in seeded.get("/api/v1/teams", headers=alpha).json()] == ["alpha"]
    projects = {p["slug"]: p for p in seeded.get("/api/v1/teams/alpha/projects", headers=alpha).json()}
    assert set(projects) == {"shop", "wiki"}
    assert (projects["shop"]["environments"], projects["shop"]["apps"]) == (2, 2)

    envs = seeded.get("/api/v1/teams/alpha/projects/shop/environments", headers=alpha).json()
    assert [(e["slug"], e["kind"], e["apps"]) for e in envs] == [
        ("production", "production", 1),
        ("preview-feature-x", "preview", 1),
    ]
    apps = _apps(seeded, alpha, "alpha")
    assert set(apps) == {"shop", "shop-pr-x", "wiki"}
    assert apps["shop-pr-x"]["environment"]["kind"] == "preview"
    assert {a["driver"] for a in apps.values()} == {"engine"}
    assert {a["team"]["slug"] for a in apps.values()} == {"alpha"}
    narrowed = _apps(seeded, alpha, "alpha", project="shop", environment="production")
    assert [(a["external_id"], a["domain"]) for a in narrowed.values()] == [("shop", "shop.test")]

    detail = seeded.get("/api/v1/teams/alpha", headers=alpha).json()
    assert detail["counts"] == {"projects": 2, "environments": 3, "apps": 3, "members": 2}


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/teams/beta",
        "/api/v1/teams/beta/projects",
        "/api/v1/teams/beta/projects/blog",
        "/api/v1/teams/beta/projects/blog/environments",
        "/api/v1/teams/beta/apps",
    ],
)
def test_other_team_answers_404(seeded, path):
    assert seeded.get(path, headers=_login(seeded, "alpha@x.test")).status_code == 404


def test_cross_team_writes_are_refused(seeded):
    alpha, beta = _login(seeded, "alpha@x.test"), _login(seeded, "beta@x.test")
    beta_app = next(iter(_apps(seeded, beta, "beta").values()))
    beta_env = beta_app["environment"]["id"]
    alpha_app = _apps(seeded, alpha, "alpha")["shop"]

    assert seeded.post("/api/v1/teams/beta/projects", headers=alpha, json={"name": "x"}).status_code == 404
    assert seeded.delete("/api/v1/teams/beta/projects/blog", headers=alpha).status_code == 404
    # Alpha's app into beta's environment, and beta's app through alpha's team.
    moved = seeded.post(f"/api/v1/teams/alpha/apps/{alpha_app['id']}/move", headers=alpha,
                        json={"environment_id": beta_env})
    assert moved.status_code == 404
    stolen = seeded.post(f"/api/v1/teams/alpha/apps/{beta_app['id']}/move", headers=alpha,
                         json={"environment_id": alpha_app["environment"]["id"]})
    assert stolen.status_code == 404
    assert seeded.get("/api/v1/platform/apps", headers=alpha).status_code == 403


def test_platform_admin_sees_every_team(seeded):
    root = _root(seeded)
    apps = seeded.get("/api/v1/platform/apps", headers=root).json()
    by_name = {a["name"]: a["team"]["slug"] for a in apps}
    assert by_name["shop"] == by_name["wiki"] == "alpha"
    assert by_name["blog"] == "beta"
    assert by_name["platform-app"] not in {"alpha", "beta"}
    assert seeded.get("/api/v1/teams/beta/projects", headers=root).status_code == 200
    assert len(seeded.get("/api/v1/teams", headers=root).json()) == 3


def test_project_and_environment_lifecycle(seeded):
    alpha = _login(seeded, "alpha@x.test")
    created = seeded.post("/api/v1/teams/alpha/projects", headers=alpha, json={"name": "New Thing"})
    assert created.status_code == 201, created.text
    assert (created.json()["slug"], created.json()["environments"]) == ("new-thing", 1)
    dup = seeded.post("/api/v1/teams/alpha/projects", headers=alpha, json={"name": "new thing"})
    assert dup.status_code == 409

    env = seeded.post("/api/v1/teams/alpha/projects/new-thing/environments", headers=alpha,
                      json={"name": "Staging"})
    assert env.status_code == 201 and env.json()["kind"] == "staging"
    renamed = seeded.patch("/api/v1/teams/alpha/projects/new-thing", headers=alpha, json={"name": "Renamed"})
    assert renamed.json()["name"] == "Renamed"

    # Placement is the user's: a move survives the next sync.
    shop = _apps(seeded, alpha, "alpha")["shop"]
    moved = seeded.post(f"/api/v1/teams/alpha/apps/{shop['id']}/move", headers=alpha,
                        json={"environment_id": env.json()["id"]})
    assert moved.status_code == 200, moved.text
    again = _apps(seeded, alpha, "alpha")["shop"]
    assert (again["project"]["slug"], again["environment"]["slug"]) == ("new-thing", "staging")

    assert seeded.delete("/api/v1/teams/alpha/projects/new-thing", headers=alpha).status_code == 409
    assert seeded.delete("/api/v1/teams/alpha/projects/new-thing/environments/staging",
                         headers=alpha).status_code == 409
    seeded.post(f"/api/v1/teams/alpha/apps/{shop['id']}/move", headers=alpha,
                json={"environment_id": shop["environment"]["id"]})
    assert seeded.delete("/api/v1/teams/alpha/projects/new-thing", headers=alpha).status_code == 204


def test_members_cannot_write(seeded):
    member = _login(seeded, "alpha-member@x.test")
    assert seeded.get("/api/v1/teams/alpha/projects", headers=member).status_code == 200
    assert seeded.post("/api/v1/teams/alpha/projects", headers=member, json={"name": "x"}).status_code == 403


def test_removed_app_is_pruned(seeded):
    alpha = _login(seeded, "alpha@x.test")
    assert "wiki" in _apps(seeded, alpha, "alpha")

    async def remove_wiki() -> None:
        async with session_scope() as session:
            await session.execute(delete(TenantResource).where(TenantResource.external_id == "wiki"))

    asyncio.run(remove_wiki())
    assert "wiki" not in _apps(seeded, alpha, "alpha")


def test_imported_app_appears_as_engine_app(seeded):
    """An import registers an engine stack; it shows up like any other engine app."""
    alpha = _login(seeded, "alpha@x.test")

    async def import_it() -> None:
        async with session_scope() as session:
            tenant = await session.scalar(select(Tenant).where(Tenant.slug == "alpha"))
            session.add(_engine_app(tenant.id, "moving-stack"))
            session.add(Deployment(tenant_id=tenant.id, project="moving-stack", domain="moving.test",
                                   builder="import"))

    asyncio.run(import_it())
    row = _apps(seeded, alpha, "alpha")["moving-stack"]
    assert (row["driver"], row["domain"], row["environment"]["kind"]) == ("engine", "moving.test", "production")

    async def count_rows() -> int:
        async with session_scope() as session:
            rows = await session.scalars(select(WorkspaceApp).where(WorkspaceApp.external_id == "moving-stack"))
            return len(rows.all())

    assert asyncio.run(count_rows()) == 1


def test_a_locked_sync_answers_from_the_existing_index(seeded, monkeypatch):
    """Parallel listings each try to index new stacks; SQLite refuses the second writer.
    That request must still answer (from the rows already indexed), not 500."""
    from sqlalchemy.exc import OperationalError

    from app.modules.workspaces.service import WorkspaceService

    alpha = _login(seeded, "alpha@x.test")
    assert "shop" in _apps(seeded, alpha, "alpha")  # first listing indexes everything

    async def locked(self):
        raise OperationalError("INSERT INTO apps", {}, Exception("database is locked"))

    monkeypatch.setattr(WorkspaceService, "sync", locked)
    assert "shop" in _apps(seeded, alpha, "alpha")
    assert seeded.get("/api/v1/teams/alpha/projects", headers=alpha).status_code == 200
