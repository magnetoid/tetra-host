"""Env var / secret storage + injection for native (Tetra Engine) deploys."""

import asyncio

import yaml

from app.db import session_scope
from app.models import AdminUser, AppEnvVar, Plan, Tenant
from app.modules.auth.service import AuthService
from app.modules.deploys.service import compose_for_image


# ── Injection (pure) ───────────────────────────────────────────────────────


def test_compose_injects_env_and_keeps_router_port():
    compose = yaml.safe_load(
        compose_for_image("img:tag", 8080, {"DATABASE_URL": "postgres://x", "PORT": "9999"})
    )
    env = compose["services"]["app"]["environment"]
    assert "PORT=8080" in env  # router port wins
    assert "PORT=9999" not in env  # user-supplied PORT is dropped
    assert "DATABASE_URL=postgres://x" in env


def test_compose_without_env_is_just_port():
    compose = yaml.safe_load(compose_for_image("img:tag", 3000))
    assert compose["services"]["app"]["environment"] == ["PORT=3000"]


# ── API (tenant-scoped, secrets masked, encrypted at rest) ─────────────────


async def _seed(*, slug: str, email: str) -> None:
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
                tenant_id=tenant.id, email=email, full_name="Owner",
                password_hash=auth.hash_password("env-pass"), is_active=True,
            )
        )


def _login(client, email: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "env-pass"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_set_list_masks_secret_and_shows_plain(client):
    asyncio.run(_seed(slug="envt", email="owner@envt.test"))
    headers = _login(client, "owner@envt.test")

    r = client.post("/api/v1/deploys/blog/env", headers=headers, json={"key": "NODE_ENV", "value": "production"})
    assert r.status_code == 200
    r = client.post(
        "/api/v1/deploys/blog/env", headers=headers,
        json={"key": "API_KEY", "value": "sk-topsecret", "is_secret": True},
    )
    assert r.status_code == 200

    rows = client.get("/api/v1/deploys/blog/env", headers=headers).json()
    by_key = {row["key"]: row for row in rows}
    assert by_key["NODE_ENV"]["value"] == "production"  # plain shown
    assert by_key["API_KEY"]["value"] == "••••••"  # secret masked
    assert by_key["API_KEY"]["is_secret"] is True


def test_secret_value_is_encrypted_at_rest(client):
    asyncio.run(_seed(slug="enc", email="owner@enc.test"))
    headers = _login(client, "owner@enc.test")
    client.post(
        "/api/v1/deploys/app/env", headers=headers,
        json={"key": "TOKEN", "value": "plain-text-secret", "is_secret": True},
    )

    async def _raw() -> str:
        async with session_scope() as session:
            from sqlalchemy import select

            row = (await session.scalars(select(AppEnvVar).where(AppEnvVar.key == "TOKEN"))).one()
            return row.value

    stored = asyncio.run(_raw())
    assert stored != "plain-text-secret"  # never persisted in plaintext
    assert "plain-text-secret" not in stored


def test_delete_env_var(client):
    asyncio.run(_seed(slug="del", email="owner@del.test"))
    headers = _login(client, "owner@del.test")
    client.post("/api/v1/deploys/app/env", headers=headers, json={"key": "GONE", "value": "v"})
    assert client.delete("/api/v1/deploys/app/env/GONE", headers=headers).status_code == 200
    assert client.get("/api/v1/deploys/app/env", headers=headers).json() == []
    # deleting a missing key → 404
    assert client.delete("/api/v1/deploys/app/env/GONE", headers=headers).status_code == 404


def test_env_is_tenant_scoped(client):
    asyncio.run(_seed(slug="ta", email="a@ta.test"))
    asyncio.run(_seed(slug="tb", email="b@tb.test"))
    headers_a = _login(client, "a@ta.test")
    headers_b = _login(client, "b@tb.test")
    client.post("/api/v1/deploys/shared/env", headers=headers_a, json={"key": "SECRET", "value": "a-only"})
    # Tenant B uses the same project name but sees none of A's vars.
    assert client.get("/api/v1/deploys/shared/env", headers=headers_b).json() == []


def test_empty_key_rejected(client):
    asyncio.run(_seed(slug="ek", email="owner@ek.test"))
    headers = _login(client, "owner@ek.test")
    assert client.post("/api/v1/deploys/app/env", headers=headers, json={"key": "  ", "value": "x"}).status_code == 422
