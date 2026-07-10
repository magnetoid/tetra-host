import asyncio
from urllib.parse import parse_qs, urlparse


import app.modules.sso.service as sso_module
from app.db import session_scope
from app.models import AdminUser, Tenant
from app.modules.auth.service import AuthService

REDIRECT_URI = "https://console.test/auth/sso/callback"

DISCOVERY = {
    "authorization_endpoint": "https://idp.test/authorize",
    "token_endpoint": "https://idp.test/token",
    "userinfo_endpoint": "https://idp.test/userinfo",
}


def _fake_idp(*, email: str = "sso-user@acme.com", verified: bool = True):
    async def fake_request_json(client, *, service, method, url, headers=None,
                                params=None, json_body=None, data=None, files=None,
                                max_attempts=3, timeout=None):
        if url.endswith("/.well-known/openid-configuration"):
            return DISCOVERY
        if url == DISCOVERY["token_endpoint"]:
            assert data["grant_type"] == "authorization_code"
            assert data["redirect_uri"] == REDIRECT_URI
            return {"access_token": "at-123", "id_token": "jwt"}
        if url == DISCOVERY["userinfo_endpoint"]:
            assert headers["Authorization"] == "Bearer at-123"
            return {"email": email, "email_verified": verified, "name": "SSO User"}
        raise AssertionError(f"unexpected url {url}")

    return fake_request_json


async def _seed() -> None:
    async with session_scope() as session:
        auth = AuthService(session)
        tenant = Tenant(name="Acme", slug="acme", status="active")
        session.add(tenant)
        await session.flush()
        session.add(AdminUser(
            tenant_id=tenant.id, email="owner@acme.test", full_name="Owner",
            password_hash=auth.hash_password("owner-password"), is_active=True,
        ))


def _login(client, email: str, password: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _configure_sso(client, owner, **overrides) -> None:
    body = {
        "issuer": "https://idp.test",
        "client_id": "client-abc",
        "client_secret": "shhh-secret",
        "allowed_domains": "acme.com",
        "default_role": "member",
        "provider_label": "Acme SSO",
        "enabled": True,
    }
    body.update(overrides)
    r = client.put("/api/v1/sso", headers=owner, json=body)
    assert r.status_code == 200, r.text


def _state_from_authorize(client) -> str:
    r = client.get("/api/v1/auth/sso/acme/authorize", params={"redirect_uri": REDIRECT_URI})
    assert r.status_code == 200, r.text
    url = r.json()["authorize_url"]
    return parse_qs(urlparse(url).query)["state"][0]


def test_config_crud_masks_secret_and_gates_to_owner(client):
    asyncio.run(_seed())
    owner = _login(client, "owner@acme.test", "owner-password")

    assert client.get("/api/v1/sso", headers=owner).json()["configured"] is False
    _configure_sso(client, owner)

    got = client.get("/api/v1/sso", headers=owner).json()
    assert got["configured"] and got["enabled"] and got["has_secret"] is True
    assert got["client_id"] == "client-abc"
    assert "client_secret" not in got  # secret never leaves the server

    # Updating with a blank secret keeps the stored one.
    _configure_sso(client, owner, client_secret="")
    assert client.get("/api/v1/sso", headers=owner).json()["has_secret"] is True


def test_full_sso_login_provisions_member(client, monkeypatch):
    asyncio.run(_seed())
    owner = _login(client, "owner@acme.test", "owner-password")
    _configure_sso(client, owner)

    monkeypatch.setattr(sso_module, "request_json", _fake_idp())
    sso_module._discovery_cache.clear()

    state = _state_from_authorize(client)
    r = client.post("/api/v1/auth/sso/callback",
                    json={"code": "auth-code", "state": state, "redirect_uri": REDIRECT_URI})
    assert r.status_code == 200, r.text
    admin = r.json()["admin"]
    assert admin["email"] == "sso-user@acme.com"
    assert admin["role"] == "member"
    assert r.json()["token"]

    # Second login for the same identity re-uses the account (no duplicate).
    state2 = _state_from_authorize(client)
    r2 = client.post("/api/v1/auth/sso/callback",
                     json={"code": "auth-code", "state": state2, "redirect_uri": REDIRECT_URI})
    assert r2.status_code == 200
    assert r2.json()["admin"]["id"] == admin["id"]


def test_sso_domain_restriction_and_bad_state(client, monkeypatch):
    asyncio.run(_seed())
    owner = _login(client, "owner@acme.test", "owner-password")
    _configure_sso(client, owner, allowed_domains="only-this.com")

    monkeypatch.setattr(sso_module, "request_json", _fake_idp(email="user@acme.com"))
    sso_module._discovery_cache.clear()

    state = _state_from_authorize(client)
    denied = client.post("/api/v1/auth/sso/callback",
                         json={"code": "c", "state": state, "redirect_uri": REDIRECT_URI})
    assert denied.status_code == 403

    # Tampered / forged state is rejected before any IdP call.
    forged = client.post("/api/v1/auth/sso/callback",
                         json={"code": "c", "state": "not-a-valid-state", "redirect_uri": REDIRECT_URI})
    assert forged.status_code == 400


def test_authorize_404_when_sso_disabled(client):
    asyncio.run(_seed())
    owner = _login(client, "owner@acme.test", "owner-password")
    _configure_sso(client, owner, enabled=False)
    r = client.get("/api/v1/auth/sso/acme/authorize", params={"redirect_uri": REDIRECT_URI})
    assert r.status_code == 404


def test_sso_config_requires_owner(client):
    asyncio.run(_seed())
    # Seed a plain member in the same tenant.
    async def _add_member() -> None:
        async with session_scope() as session:
            auth = AuthService(session)
            tenant = (await AuthService(session).get_tenant_by_slug("acme"))
            session.add(AdminUser(
                tenant_id=tenant.id, email="member@acme.test", full_name="Member",
                password_hash=auth.hash_password("member-password"), is_active=True, role="member",
            ))
    asyncio.run(_add_member())
    member = _login(client, "member@acme.test", "member-password")
    assert client.get("/api/v1/sso", headers=member).status_code == 403
    assert client.put("/api/v1/sso", headers=member, json={"issuer": "x"}).status_code == 403
