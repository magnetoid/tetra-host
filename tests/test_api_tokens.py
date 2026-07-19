"""Personal API tokens: create (shown once) → list → authenticate → revoke.

Exercises both the service (unit) and the /account/tokens endpoints, plus the
key integration guarantee: a minted token authenticates real API calls and stops
working the moment it's revoked or expired.
"""

import asyncio
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import session_scope
from app.models import AdminUser
from app.services.api_tokens import ApiTokenService, TOKEN_PREFIX, hash_token


def _login(client: TestClient) -> dict[str, str]:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "supersecurepassword"},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['token']}"}


async def _admin(session):
    return (
        await session.scalars(select(AdminUser).where(AdminUser.email == "admin@example.com"))
    ).first()


# ── service unit ───────────────────────────────────────────────────────────


def test_service_create_hashes_and_reveals_once(client: TestClient):
    # `client` boots the app + seeds the bootstrap admin.
    async def _run():
        async with session_scope() as session:
            created = await ApiTokenService(session).create(admin=await _admin(session), name="ci")
            return created.secret, created.row.token_hash, created.row.prefix

    secret, stored_hash, prefix = asyncio.run(_run())
    assert secret.startswith(TOKEN_PREFIX)
    assert stored_hash == hash_token(secret)  # only the hash is stored
    assert secret != stored_hash
    assert prefix and secret.startswith(prefix)


def test_service_expired_token_rejected(client: TestClient):
    async def _run():
        async with session_scope() as session:
            svc = ApiTokenService(session)
            created = await svc.create(admin=await _admin(session), name="temp")
            # Force it into the past, then authenticate → must be rejected.
            created.row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
            await session.flush()
            return await svc.authenticate(created.secret)

    assert asyncio.run(_run()) is None


# ── endpoint lifecycle ─────────────────────────────────────────────────────


def test_tokens_require_auth(client: TestClient):
    assert client.get("/api/v1/account/tokens").status_code == 401


def test_create_list_and_revoke(client: TestClient):
    headers = _login(client)

    # create → secret shown once
    created = client.post("/api/v1/account/tokens", headers=headers, json={"name": "laptop"})
    assert created.status_code == 201, created.text
    body = created.json()
    secret = body["token"]
    assert secret.startswith(TOKEN_PREFIX)
    assert body["name"] == "laptop"
    token_id = body["id"]

    # list → present, and never leaks the secret
    listed = client.get("/api/v1/account/tokens", headers=headers)
    assert listed.status_code == 200
    rows = listed.json()
    assert any(r["id"] == token_id for r in rows)
    assert all("token" not in r for r in rows)

    # the minted token authenticates a real API call
    who = client.get("/api/v1/account/tokens", headers={"Authorization": f"Bearer {secret}"})
    assert who.status_code == 200

    # revoke → gone from the list, and the token stops working
    revoked = client.delete(f"/api/v1/account/tokens/{token_id}", headers=headers)
    assert revoked.status_code == 200
    after = client.get("/api/v1/account/tokens", headers={"Authorization": f"Bearer {secret}"})
    assert after.status_code == 401


def test_revoke_unknown_is_404(client: TestClient):
    headers = _login(client)
    assert client.delete("/api/v1/account/tokens/does-not-exist", headers=headers).status_code == 404
