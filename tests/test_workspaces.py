"""Team → project → environment → app hierarchy: indexing, placement and team isolation."""

import asyncio
import os

import pytest
from sqlalchemy import select

from app.db import session_scope
from app.models import (
    AdminUser,
    Deployment,
    ImportRun,
    PreviewEnv,
    Tenant,
    TenantResource,
    WorkspaceApp,
)
from app.models.admin import ROLE_OWNER
from app.models.import_run import IMPORT_LIVE
from app.models.team import ROLE_MEMBER
from app.models.tenant_resource import PROVIDER_COOLIFY, RESOURCE_TYPE_SITE
from app.modules.auth.service import AuthService
from app.services.coolify import CoolifyApplication, CoolifyClient
from app.services.http import ProviderAPIError

PASSWORD = "tenant-password"


def _coolify_app(uuid: str, name: str, project: str, env: str = "production") -> CoolifyApplication:
    return CoolifyApplication(
        id=uuid, name=name, primary_domain=f"{name}.test", status="running", repository="",
        environment=env, updated_at="", project_name=project,
    )


class CoolifyStub:
    def __init__(self) -> None:
        self.apps = [
            _coolify_app("c-alpha", "alpha-site", "Alpha Co"),
            _coolify_app("c-platform", "platform-site", "Marketing", env="staging"),
            _coolify_app("c-moving", "moving-site", "Marketing"),
        ]
        self.fail = False

    async def list_applications(self, refresh: bool = False):
        if self.fail:
            raise ProviderAPIError(service="Coolify", message="down", status_code=502)
        return list(self.apps)


@pytest.fixture
def coolify(monkeypatch) -> CoolifyStub:
    stub = CoolifyStub()
    monkeypatch.setattr(CoolifyClient, "is_configured", lambda self: True)
    monkeypatch.setattr(CoolifyClient, "list_applications", lambda self, refresh=False: stub.list_applications())
    return stub


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
                session.add(TenantResource(
                    tenant_id=tenant.id, provider=PROVIDER_COOLIFY,
                    resource_type=RESOURCE_TYPE_SITE, external_id="c-alpha", display_name="alpha",
                ))
                session.add(Deployment(tenant_id=tenant.id, project="shop", domain="shop.test", status="ready"))
                session.add(Deployment(tenant_id=tenant.id, project="shop-pr-x", domain="x.shop.test"))
                session.add(PreviewEnv(
                    tenant_id=tenant.id, project="shop", branch="feature/x",
                    preview_project="shop-pr-x", domain="x.shop.test",
                ))
            else:
                session.add(Deployment(tenant_id=tenant.id, project="blog", domain="blog.test"))


def _login(client, email: str, password: str = PASSWORD) -> dict[str, str]:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['token']}"}


def _root(client) -> dict[str, str]:
    return _login(client, os.environ["ADMIN_BOOTSTRAP_EMAIL"], os.environ["ADMIN_BOOTSTRAP_PASSWORD"])


@pytest.fixture
def seeded(client, coolify):
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
    assert set(projects) == {"shop", "alpha-co"}
    assert (projects["shop"]["environments"], projects["shop"]["apps"]) == (2, 2)

    envs = seeded.get("/api/v1/teams/alpha/projects/shop/environments", headers=alpha).json()
    assert [(e["slug"], e["kind"], e["apps"]) for e in envs] == [
        ("production", "production", 1),
        ("preview-feature-x", "preview", 1),
    ]
    apps = _apps(seeded, alpha, "alpha")
    assert set(apps) == {"shop", "shop-pr-x", "alpha-site"}
    assert apps["shop-pr-x"]["environment"]["kind"] == "preview"
    assert apps["alpha-site"]["driver"] == "coolify"
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
    assert by_name["shop"] == by_name["alpha-site"] == "alpha"
    assert by_name["blog"] == "beta"
    # Unassigned Coolify apps belong to the platform team.
    platform_slug = by_name["platform-site"]
    assert platform_slug not in {"alpha", "beta"}
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


def test_coolify_outage_keeps_rows_and_flags_response(seeded, coolify):
    root = _root(seeded)
    first = seeded.get("/api/v1/platform/apps", headers=root)
    coolify.fail = True
    second = seeded.get("/api/v1/platform/apps", headers=root)
    assert second.headers.get("X-Tetra-Degraded") == "coolify"
    assert {a["name"] for a in second.json()} == {a["name"] for a in first.json()}

    coolify.fail = False
    coolify.apps = [a for a in coolify.apps if a.id != "c-platform"]
    pruned = {a["name"] for a in seeded.get("/api/v1/platform/apps", headers=root).json()}
    assert "platform-site" not in pruned and "alpha-site" in pruned


def test_imported_app_keeps_its_row(seeded):
    root = _root(seeded)
    before = {a["name"]: a for a in seeded.get("/api/v1/platform/apps", headers=root).json()}
    moving = before["moving-site"]
    assert moving["driver"] == "coolify"

    async def import_it() -> None:
        async with session_scope() as session:
            tenant_id = (await session.scalar(select(WorkspaceApp).where(WorkspaceApp.id == moving["id"]))).tenant_id
            session.add(ImportRun(tenant_id=tenant_id, source="coolify", source_ref="c-moving",
                                  project="moving-stack", state=IMPORT_LIVE))
            session.add(Deployment(tenant_id=tenant_id, project="moving-stack", domain="moving.test"))

    asyncio.run(import_it())
    after = {a["id"]: a for a in seeded.get("/api/v1/platform/apps", headers=root).json()}
    row = after[moving["id"]]
    assert (row["driver"], row["external_id"], row["domain"]) == ("engine", "moving-stack", "moving.test")
    assert row["environment"]["id"] == moving["environment"]["id"]
    assert sum(1 for a in after.values() if a["external_id"] == "moving-stack") == 1
