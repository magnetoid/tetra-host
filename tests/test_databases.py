"""Managed databases: create on the tenant network, connect, link, back up, restore, isolate."""

import asyncio
import gzip
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from sqlalchemy import select

from app.config import get_settings
from app.db import session_scope
from app.models import AdminUser, AppEnvVar, Plan, Tenant, TenantResource
from app.models.database import DatabaseBackup, ManagedDatabase
from app.models.tenant_resource import PROVIDER_DOCKER, RESOURCE_TYPE_APP
from app.modules.auth.service import AuthService
from app.modules.databases.service import DatabasesService, run_scheduled_backups
from app.services import db_engines
from app.services.docker_engine import DockerEngine, DockerEngineError
from app.services.secrets import decrypt
from app.services.tenant_network import apply_tenant_network, tenant_network_name

DUMP = b"-- dump\nCREATE TABLE posts (id int);\n"


# ── pure helpers ──────────────────────────────────────────────────


def test_names_are_validated():
    assert db_engines.validate_name(" Blog-DB ") == "blog-db"
    for bad in ["ab", "1blog", "blog_db", "blog--db", "-blog", "app", "x" * 40]:
        with pytest.raises(db_engines.InvalidDatabaseSpec):
            db_engines.validate_name(bad)


def test_engine_and_version_are_validated():
    spec, version = db_engines.resolve_engine("Postgres", None)
    assert (spec.key, version) == ("postgres", "17")
    with pytest.raises(db_engines.InvalidDatabaseSpec):
        db_engines.resolve_engine("oracle", None)
    with pytest.raises(db_engines.InvalidDatabaseSpec):
        db_engines.resolve_engine("postgres", "9.6")


def test_compose_publishes_no_port_and_joins_the_tenant_network():
    spec, version = db_engines.resolve_engine("postgres", "16")
    creds = db_engines.new_credentials(spec, "blog-db")
    doc = yaml.safe_load(
        db_engines.compose_for_database(
            spec, version, name="blog-db", creds=creds, network="tetra-t-abc", mem_mb=256
        )
    )
    svc = doc["services"]["db"]
    assert svc["image"] == "postgres:16-alpine"
    assert "ports" not in svc
    assert svc["networks"] == {"tenant": {"aliases": ["blog-db"]}}
    assert doc["networks"]["tenant"] == {"name": "tetra-t-abc", "external": True}
    assert svc["volumes"] == ["data:/var/lib/postgresql/data"]
    assert svc["mem_limit"] == "256m"
    assert svc["environment"]["POSTGRES_DB"] == "blog_db"


def test_connection_url_escapes_the_password():
    spec = db_engines.ENGINES["mysql"]
    url = db_engines.connection_url(
        spec, host="shop", creds={"user": "shop", "password": "a/b@c", "database": "shop"}
    )
    assert url == "mysql://shop:a%2Fb%40c@shop:3306/shop"
    redis = db_engines.connection_url(db_engines.ENGINES["redis"], host="cache", creds={"password": "p"})
    assert redis == "redis://:p@cache:6379/0"


def test_apply_tenant_network_keeps_the_default_network():
    compose = yaml.safe_dump({"services": {"app": {"image": "x"}}})
    doc = yaml.safe_load(apply_tenant_network(compose, "tetra-t-abc"))
    assert doc["services"]["app"]["networks"] == ["default", "tetra-tenant"]
    assert doc["networks"]["tetra-tenant"] == {"name": "tetra-t-abc", "external": True}
    assert apply_tenant_network(compose, "") == compose


def test_tenant_network_name_is_short_and_stable():
    assert tenant_network_name("0b8e5c9a-1234-4bcd-9abc-def012345678") == "tetra-t-0b8e5c9a1234"
    assert tenant_network_name(None) == "tetra-t-platform"


def test_ensure_network_creates_only_when_missing():
    calls: list[list[str]] = []

    async def runner(argv, stdin, env):
        calls.append(argv[1:])
        if argv[1:3] == ["network", "inspect"] and argv[3] == "missing":
            return 1, "", "Error: No such network"
        return 0, "", ""

    engine = DockerEngine(runner=runner)
    asyncio.run(engine.ensure_network("present"))
    asyncio.run(engine.ensure_network("missing", labels={"tetra.tenant": "t1"}))
    creates = [c for c in calls if c[:2] == ["network", "create"]]
    assert creates == [
        ["network", "create", "--driver", "bridge", "--label", "tetra.tenant=t1", "missing"]
    ]


# ── API ───────────────────────────────────────────────────────────


async def _seed(slug: str, *, app: str | None = None) -> str:
    async with session_scope() as session:
        plan = Plan(key=f"plan_{slug}", name="P", max_apps=5)
        session.add(plan)
        await session.flush()
        tenant = Tenant(name=slug, slug=slug, status="active", plan_id=plan.id)
        session.add(tenant)
        await session.flush()
        session.add(
            AdminUser(
                tenant_id=tenant.id, email=f"o@{slug}.test", full_name="Owner",
                password_hash=AuthService(session).hash_password("db-pass"), is_active=True,
            )
        )
        if app:
            session.add(
                TenantResource(
                    tenant_id=tenant.id, provider=PROVIDER_DOCKER,
                    resource_type=RESOURCE_TYPE_APP, external_id=app, display_name=app,
                )
            )
        return tenant.id


def _headers(client, slug: str) -> dict[str, str]:
    token = client.post(
        "/api/v1/auth/login", json={"email": f"o@{slug}.test", "password": "db-pass"}
    ).json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def engine_fakes(monkeypatch, tmp_path):
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_provider_actions", True)
    monkeypatch.setattr(settings, "database_backup_dir", str(tmp_path / "backups"))
    state: dict = {"deployed": {}, "removed": [], "networks": [], "restored": [], "fail_dump": False}

    async def deploy_stack(self, project, compose, env=None):
        state["deployed"][project] = compose
        return {"ok": True, "project": project}

    async def remove_stack(self, project, *, volumes=False):
        state["removed"].append((project, volumes))
        return {"ok": True}

    async def ensure_network(self, name, *, labels=None):
        state["networks"].append(name)

    async def list_stacks(self):
        return [{"Name": p, "Status": "running(1)"} for p in state["deployed"]]

    async def exec_to_gzip(self, project, service, script, path):
        if state["fail_dump"]:
            raise DockerEngineError(message="pg_dump: connection refused (exit 1)", code=502)
        with gzip.open(path, "wb") as fh:
            fh.write(DUMP)

    async def exec_from_gzip(self, project, service, script, path):
        with gzip.open(path, "rb") as fh:
            state["restored"].append((project, script, fh.read()))

    for name, fn in {
        "deploy_stack": deploy_stack, "remove_stack": remove_stack,
        "ensure_network": ensure_network, "list_stacks": list_stacks,
        "exec_to_gzip": exec_to_gzip, "exec_from_gzip": exec_from_gzip,
    }.items():
        monkeypatch.setattr(DockerEngine, name, fn)
    state["backup_dir"] = tmp_path / "backups"
    return state


def _wait(client, url, headers, done, timeout=5.0):
    deadline = time.monotonic() + timeout
    while True:
        body = client.get(url, headers=headers).json()
        if done(body):
            return body
        if time.monotonic() > deadline:
            raise AssertionError(f"not reached: {body}")
        time.sleep(0.02)


def test_create_connect_and_link(client, engine_fakes):
    tenant_id = asyncio.run(_seed("acme", app="blog"))
    h = _headers(client, "acme")

    r = client.post("/api/v1/databases", json={"name": "blog-db", "engine": "postgres"}, headers=h)
    assert r.status_code == 201, r.text
    db = r.json()
    assert (db["host"], db["port"], db["version"], db["backup_cron"]) == ("blog-db", 5432, "17", "0 3 * * *")
    assert engine_fakes["networks"] == [tenant_network_name(tenant_id)]
    (project, compose), = engine_fakes["deployed"].items()
    assert project.startswith("tdb-") and "blog-db" in compose

    listed = client.get("/api/v1/databases", headers=h).json()
    assert [(d["name"], d["status"]) for d in listed] == [("blog-db", "running(1)")]

    conn = client.get(f"/api/v1/databases/{db['id']}/connection", headers=h).json()
    assert conn["url"] == f"postgresql://blog_db:{conn['password']}@blog-db:5432/blog_db"

    dup = client.post("/api/v1/databases", json={"name": "blog-db", "engine": "mysql"}, headers=h)
    assert dup.status_code == 409

    linked = client.post(
        f"/api/v1/databases/{db['id']}/link", json={"project": "blog"}, headers=h
    )
    assert linked.status_code == 200, linked.text

    async def env_value():
        async with session_scope() as session:
            row = await session.scalar(select(AppEnvVar).where(AppEnvVar.project == "blog"))
            return row.key, decrypt(row.value), row.is_secret

    assert asyncio.run(env_value()) == ("DATABASE_URL", conn["url"], True)

    foreign = client.post(
        f"/api/v1/databases/{db['id']}/link", json={"project": "not-mine"}, headers=h
    )
    assert foreign.status_code == 403


def test_databases_are_tenant_isolated(client, engine_fakes):
    asyncio.run(_seed("acme"))
    asyncio.run(_seed("rival"))
    acme, rival = _headers(client, "acme"), _headers(client, "rival")
    db = client.post("/api/v1/databases", json={"name": "shop", "engine": "mysql"}, headers=acme).json()

    assert client.get("/api/v1/databases", headers=rival).json() == []
    for method, path in [
        ("get", f"/api/v1/databases/{db['id']}"),
        ("get", f"/api/v1/databases/{db['id']}/connection"),
        ("get", f"/api/v1/databases/{db['id']}/backups"),
        ("post", f"/api/v1/databases/{db['id']}/backups"),
        ("post", f"/api/v1/databases/{db['id']}/stop"),
        ("delete", f"/api/v1/databases/{db['id']}"),
    ]:
        assert getattr(client, method)(path, headers=rival).status_code == 404, path
    # Same name in another tenant is fine: names are per tenant.
    other = client.post("/api/v1/databases", json={"name": "shop", "engine": "mysql"}, headers=rival)
    assert other.status_code == 201


def test_quota_and_disabled_actions(client, engine_fakes, monkeypatch):
    asyncio.run(_seed("acme"))
    h = _headers(client, "acme")
    monkeypatch.setattr(get_settings(), "max_databases_per_tenant", 1)
    assert client.post("/api/v1/databases", json={"name": "one", "engine": "redis"}, headers=h).status_code == 201
    over = client.post("/api/v1/databases", json={"name": "two", "engine": "redis"}, headers=h)
    assert over.status_code == 402
    monkeypatch.setattr(get_settings(), "enable_provider_actions", False)
    blocked = client.post("/api/v1/databases", json={"name": "three", "engine": "redis"}, headers=h)
    assert blocked.status_code == 403
    bad = client.post("/api/v1/databases", json={"name": "Bad_Name", "engine": "redis"}, headers=h)
    assert bad.status_code in {403, 422}


def test_backup_restore_and_delete(client, engine_fakes):
    asyncio.run(_seed("acme"))
    h = _headers(client, "acme")
    db = client.post("/api/v1/databases", json={"name": "blog-db", "engine": "postgres"}, headers=h).json()
    base = f"/api/v1/databases/{db['id']}"

    started = client.post(f"{base}/backups", headers=h)
    assert started.status_code == 202, started.text
    backups = _wait(client, f"{base}/backups", h, lambda b: b and b[0]["status"] != "running")
    backup = backups[0]
    assert backup["status"] == "ok" and backup["size_bytes"] > 0 and backup["trigger"] == "manual"
    files = list(Path(engine_fakes["backup_dir"]).rglob("*.sql.gz"))
    assert len(files) == 1 and gzip.decompress(files[0].read_bytes()) == DUMP

    restore = client.post(f"{base}/backups/{backup['id']}/restore", headers=h)
    assert restore.status_code == 202, restore.text
    _wait(client, f"{base}/backups", h, lambda b: b[0]["restore_status"] == "ok")
    (project, script, data), = engine_fakes["restored"]
    assert data == DUMP and script.startswith("psql")

    removed = client.delete(base, headers=h)
    assert removed.status_code == 200
    assert engine_fakes["removed"] == [(project, True)]
    assert not list(Path(engine_fakes["backup_dir"]).rglob("*.sql.gz"))
    assert client.get(base, headers=h).status_code == 404


def test_failed_backup_is_recorded_and_redis_has_no_backups(client, engine_fakes):
    asyncio.run(_seed("acme"))
    h = _headers(client, "acme")
    engine_fakes["fail_dump"] = True
    db = client.post("/api/v1/databases", json={"name": "blog-db", "engine": "mariadb"}, headers=h).json()
    client.post(f"/api/v1/databases/{db['id']}/backups", headers=h)
    backups = _wait(
        client, f"/api/v1/databases/{db['id']}/backups", h,
        lambda b: b and b[0]["status"] != "running",
    )
    assert backups[0]["status"] == "error" and "connection refused" in backups[0]["error"]
    restore = client.post(f"/api/v1/databases/{db['id']}/backups/{backups[0]['id']}/restore", headers=h)
    assert restore.status_code == 409

    cache = client.post("/api/v1/databases", json={"name": "cache", "engine": "redis"}, headers=h).json()
    assert cache["supports_backup"] is False and cache["backup_cron"] == ""
    assert client.post(f"/api/v1/databases/{cache['id']}/backups", headers=h).status_code == 422
    assert client.patch(
        f"/api/v1/databases/{cache['id']}", json={"backup_cron": "0 * * * *"}, headers=h
    ).status_code == 422


def test_schedule_update_and_scheduled_backups_prune(client, engine_fakes):
    asyncio.run(_seed("acme"))
    h = _headers(client, "acme")
    db = client.post("/api/v1/databases", json={"name": "blog-db", "engine": "postgres"}, headers=h).json()
    base = f"/api/v1/databases/{db['id']}"
    assert client.patch(base, json={"backup_cron": "nope"}, headers=h).status_code == 422
    updated = client.patch(base, json={"backup_cron": "0 3 * * *", "backup_keep": 2}, headers=h)
    assert updated.json()["backup_keep"] == 2

    async def scheduled_round(minute: int) -> None:
        assert await run_scheduled_backups(datetime(2026, 11, 13, 3, 0, tzinfo=UTC)) == 1
        for _ in range(200):
            async with session_scope() as session:
                running = await session.scalar(
                    select(DatabaseBackup).where(DatabaseBackup.status == "running")
                )
            if running is None:
                return
            await asyncio.sleep(0.01)

    async def rounds() -> list[DatabaseBackup]:
        for minute in range(3):
            await scheduled_round(minute)
            await asyncio.sleep(1.05)  # distinct timestamps in the file name
        assert await run_scheduled_backups(datetime(2026, 11, 13, 4, 0, tzinfo=UTC)) == 0
        await asyncio.sleep(0.2)  # let the last prune finish
        async with session_scope() as session:
            return list((await session.scalars(select(DatabaseBackup))).all())

    kept = asyncio.run(rounds())
    assert len(kept) == 2 and {b.trigger for b in kept} == {"scheduled"}
    assert len(list(Path(engine_fakes["backup_dir"]).rglob("*.sql.gz"))) == 2


def test_deploys_join_the_tenant_network_only_with_a_database(client, engine_fakes):
    from app.modules.deploys.service import DeploysService

    tenant_id = asyncio.run(_seed("acme"))
    service = DeploysService(None)
    assert asyncio.run(service._tenant_network(tenant_id)) == ""

    async def add_db() -> None:
        async with session_scope() as session:
            session.add(
                ManagedDatabase(
                    tenant_id=tenant_id, name="blog-db", engine="postgres", version="17",
                    project="tdb-test",
                )
            )

    asyncio.run(add_db())
    assert asyncio.run(service._tenant_network(tenant_id)) == tenant_network_name(tenant_id)


def test_service_status_survives_docker_outage(client, engine_fakes, monkeypatch):
    asyncio.run(_seed("acme"))
    h = _headers(client, "acme")
    client.post("/api/v1/databases", json={"name": "blog-db", "engine": "postgres"}, headers=h)

    async def down(self):
        raise DockerEngineError(message="Docker is not available", code=503)

    monkeypatch.setattr(DockerEngine, "list_stacks", down)
    listed = client.get("/api/v1/databases", headers=h).json()
    assert listed[0]["status"] == "unknown"
    assert DatabasesService  # imported for the module's public surface
