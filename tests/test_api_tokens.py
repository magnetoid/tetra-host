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


def test_read_only_token_can_read_but_not_write(client: TestClient):
    headers = _login(client)
    created = client.post(
        "/api/v1/account/tokens", headers=headers, json={"name": "ci-ro", "read_only": True}
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["scope"] == "read"
    ro = {"Authorization": f"Bearer {body['token']}"}

    # GET works…
    assert client.get("/api/v1/account/tokens", headers=ro).status_code == 200
    # …but any state change is rejected with 403 (read-only), before the handler runs.
    denied = client.post("/api/v1/account/tokens", headers=ro, json={"name": "nope"})
    assert denied.status_code == 403, denied.text
    assert "read-only" in denied.json()["detail"].lower()


def test_full_scope_is_the_default(client: TestClient):
    headers = _login(client)
    body = client.post("/api/v1/account/tokens", headers=headers, json={"name": "def"}).json()
    assert body["scope"] == "full"


def test_pat_requests_carry_ratelimit_headers(client: TestClient):
    headers = _login(client)
    secret = client.post("/api/v1/account/tokens", headers=headers, json={"name": "rl"}).json()["token"]
    resp = client.get("/api/v1/account/tokens", headers={"Authorization": f"Bearer {secret}"})
    assert resp.status_code == 200
    assert resp.headers.get("X-RateLimit-Limit")
    assert "X-RateLimit-Remaining" in resp.headers


def test_session_auth_is_not_rate_limited(client: TestClient):
    # Console/session (login-minted) token: no rate-limit headers, never throttled.
    headers = _login(client)
    resp = client.get("/api/v1/account/tokens", headers=headers)
    assert resp.status_code == 200
    assert "X-RateLimit-Limit" not in resp.headers


def test_pat_over_limit_returns_429(client: TestClient, monkeypatch):
    from app.rate_limit import RateLimitDecision

    headers = _login(client)
    secret = client.post("/api/v1/account/tokens", headers=headers, json={"name": "rl2"}).json()["token"]

    async def _deny(key, limit, window_seconds):
        return RateLimitDecision(allowed=False, retry_after_seconds=42, remaining=0)

    monkeypatch.setattr(client.app.state.rate_limiter, "check", _deny)
    resp = client.get("/api/v1/account/tokens", headers={"Authorization": f"Bearer {secret}"})
    assert resp.status_code == 429
    assert resp.headers.get("Retry-After") == "42"


def test_revoke_unknown_is_404(client: TestClient):
    headers = _login(client)
    assert client.delete("/api/v1/account/tokens/does-not-exist", headers=headers).status_code == 404


def test_create_and_revoke_are_audited(client: TestClient):
    headers = _login(client)
    token_id = client.post("/api/v1/account/tokens", headers=headers, json={"name": "audited"}).json()["id"]
    client.delete(f"/api/v1/account/tokens/{token_id}", headers=headers)

    async def _actions():
        from sqlalchemy import select

        from app.models import AuditEvent

        async with session_scope() as session:
            rows = (await session.scalars(select(AuditEvent.action))).all()
            return set(rows)

    actions = asyncio.run(_actions())
    assert "api_token.create" in actions
    assert "api_token.revoke" in actions
