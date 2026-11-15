"""Service references: ``${{service.field}}`` in env vars, scoped to the app's environment
and filled in at deploy time (ADR 0019)."""

import asyncio

import pytest

from app.modules.deploys.service import DeploysService
from app.modules.workspaces.references import Reference, find_references, substitute
from app.services.docker_engine import DockerEngineError
from tests.test_databases import _headers, _seed, engine_fakes  # noqa: F401  (fixture)

# ── parsing (pure) ────────────────────────────────────────────────


def test_find_references_dedupes_and_ignores_lookalikes():
    value = "${{shop-db.url}} ${{ shop-db.host }}:${{shop-db.port}} ${{shop-db.url}}"
    assert [str(r) for r in find_references(value)] == ["shop-db.url", "shop-db.host", "shop-db.port"]
    for plain in ["", "${shop-db.url}", "{{shop-db.url}}", "${{Shop.url}}", "${{shop-db}}", "$HOME"]:
        assert find_references(plain) == []


def test_substitute_fills_every_reference():
    values = {("db", "host"): "db", ("db", "port"): "5432"}
    out = substitute("tcp://${{db.host}}:${{ db.port }}/x", lambda r: values[(r.service, r.field)])
    assert out == "tcp://db:5432/x"
    assert str(Reference("db", "url")) == "db.url"


# ── API + deploy ──────────────────────────────────────────────────


def _setup(client):
    """Team acme with app 'blog' and a Postgres database in blog's environment."""
    tenant_id = asyncio.run(_seed("acme", app="blog"))
    h = _headers(client, "acme")
    services = {a["name"]: a for a in client.get("/api/v1/teams/acme/apps", headers=h).json()}
    env = services["blog"]["environment"]
    db = client.post(
        "/api/v1/databases",
        json={"name": "blog-db", "engine": "postgres", "environment_id": env["id"]},
        headers=h,
    )
    assert db.status_code == 201, db.text
    return tenant_id, h, db.json(), env


def test_references_list_and_validate(client, engine_fakes):  # noqa: F811
    _, h, _, _ = _setup(client)

    targets = client.get("/api/v1/deploys/blog/references", headers=h).json()
    assert targets == [{
        "service": "blog-db", "kind": "database", "engine": "postgres",
        "fields": ["url", "host", "port", "user", "password", "database"],
    }]

    ok = client.post(
        "/api/v1/deploys/blog/env", headers=h,
        json={"key": "DATABASE_URL", "value": "${{blog-db.url}}", "is_secret": True},
    )
    assert ok.status_code == 200, ok.text
    (row,) = ok.json()
    # Masked like any secret, but the reference it makes is still shown.
    assert (row["value"], row["references"]) == ("••••••", ["blog-db.url"])

    missing = client.post(
        "/api/v1/deploys/blog/env", headers=h, json={"key": "X", "value": "${{nope.url}}"}
    )
    assert missing.status_code == 422
    assert "no service named 'nope'" in missing.json()["detail"]

    field = client.post(
        "/api/v1/deploys/blog/env", headers=h, json={"key": "X", "value": "${{blog-db.colour}}"}
    )
    assert field.status_code == 422
    assert "use one of: url, host" in field.json()["detail"]


def test_deploy_fills_in_current_values(client, engine_fakes):  # noqa: F811
    tenant_id, h, db, _ = _setup(client)
    for key, value in {
        "DATABASE_URL": "${{blog-db.url}}",
        "DB_ADDR": "${{blog-db.host}}:${{blog-db.port}}",
        "PLAIN": "unchanged",
    }.items():
        assert client.post(
            "/api/v1/deploys/blog/env", headers=h, json={"key": key, "value": value}
        ).status_code == 200

    conn = client.get(f"/api/v1/databases/{db['id']}/connection", headers=h).json()
    env = asyncio.run(DeploysService(None).env_map_for_deploy(tenant_id, "blog"))
    assert env == {"DATABASE_URL": conn["url"], "DB_ADDR": "blog-db:5432", "PLAIN": "unchanged"}


def test_a_reference_broken_later_fails_the_deploy(client, engine_fakes):  # noqa: F811
    tenant_id, h, db, _ = _setup(client)
    client.post("/api/v1/deploys/blog/env", headers=h, json={"key": "U", "value": "${{blog-db.url}}"})
    assert client.delete(f"/api/v1/databases/{db['id']}", headers=h).status_code in (200, 204)

    with pytest.raises(DockerEngineError) as err:
        asyncio.run(DeploysService(None).env_map_for_deploy(tenant_id, "blog"))
    assert err.value.code == 422
    assert "no service named 'blog-db'" in err.value.message


def test_only_the_apps_own_environment_is_reachable(client, engine_fakes):  # noqa: F811
    _, h, _, _ = _setup(client)
    # sync indexed the 'blog' stack as project 'blog' (production); add a staging env.
    staging = client.post(
        "/api/v1/teams/acme/projects/blog/environments",
        json={"name": "Staging", "kind": "staging"},
        headers=h,
    )
    assert staging.status_code == 201, staging.text
    client.post(
        "/api/v1/databases",
        json={"name": "stage-db", "engine": "mysql", "environment_id": staging.json()["id"]},
        headers=h,
    )

    names = [t["service"] for t in client.get("/api/v1/deploys/blog/references", headers=h).json()]
    assert names == ["blog-db"]
    other_env = client.post(
        "/api/v1/deploys/blog/env", headers=h, json={"key": "X", "value": "${{stage-db.url}}"}
    )
    assert other_env.status_code == 422


def test_another_teams_database_is_never_reachable(client, engine_fakes):  # noqa: F811
    _setup(client)
    asyncio.run(_seed("rival", app="site"))
    rival = _headers(client, "rival")
    assert client.get("/api/v1/deploys/site/references", headers=rival).json() == []
    assert client.post(
        "/api/v1/deploys/site/env", headers=rival, json={"key": "X", "value": "${{blog-db.url}}"}
    ).status_code == 422
