"""OIDC Identity Provider — Tetra as IdP for Mailcow passwordless webmail.

Covers the signing key (RS256 + JWKS), dormancy when unconfigured, the full
browser flow (launch → authorize → token → userinfo), id_token verifiability
against the published JWK, and the security invariants: exact redirect_uri
allowlist, client-secret auth, single-use codes, and mailbox ownership gating.
"""

import asyncio
import base64
import json
import re

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers

from app.config import get_settings
from app.db import session_scope
from app.models import AdminUser, Plan, Tenant, TenantResource
from app.models.tenant_resource import PROVIDER_MAILCOW, RESOURCE_TYPE_MAILBOX
from app.modules.auth.service import AuthService
from app.services.oidc_keys import OIDCSigningKey


# Inlined — a module-level `from tests.conftest import …` re-executes conftest,
# clearing the settings cache mid-run and contaminating other tests (documented
# in tests/test_html_isolation.py). Keep this local.
def _extract_csrf(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match is not None
    return match.group(1)

REDIRECT = "https://mail.test/oidc/callback"
ISSUER = "https://panel.test"
CLIENT_ID = "mailcow"
CLIENT_SECRET = "s3cret-client"

# One RSA key for the whole module (generation is the slow part).
_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PEM = _KEY.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
).decode("utf-8")


def _b64url_decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _enable_oidc(monkeypatch, *, webmail="https://mail.test/sso"):
    s = get_settings()
    monkeypatch.setattr(s, "oidc_issuer", ISSUER)
    monkeypatch.setattr(s, "oidc_private_key_pem", _PEM)
    monkeypatch.setattr(s, "oidc_client_id", CLIENT_ID)
    monkeypatch.setattr(s, "oidc_client_secret", CLIENT_SECRET)
    monkeypatch.setattr(s, "oidc_redirect_uris_raw", REDIRECT)
    monkeypatch.setattr(s, "oidc_webmail_url", webmail)


async def _seed(*, slug, email, mailboxes=()):
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
                tenant_id=tenant.id, email=email, full_name="Owner", role="owner",
                password_hash=auth.hash_password("oidc-pass"), is_active=True,
            )
        )
        for username in mailboxes:
            session.add(
                TenantResource(
                    tenant_id=tenant.id, provider=PROVIDER_MAILCOW,
                    resource_type=RESOURCE_TYPE_MAILBOX, external_id=username,
                    display_name=username,
                )
            )
        return tenant.id


def _session_login(client, email):
    """Establish a panel session cookie (OIDC uses cookie auth, not bearer)."""
    page = client.get("/auth/login")
    csrf = _extract_csrf(page.text)
    r = client.post(
        "/auth/login",
        data={"email": email, "password": "oidc-pass", "csrf_token": csrf, "next_url": "/dashboard"},
        follow_redirects=False,
    )
    assert r.status_code == 303


# ── signing key ──────────────────────────────────────────────────────────────


def test_signing_key_signs_verifiable_rs256_and_publishes_jwk():
    key = OIDCSigningKey.from_pem(_PEM)
    token = key.sign_jwt({"sub": "info@acme.test", "iss": ISSUER})
    header_b64, payload_b64, sig_b64 = token.split(".")

    header = json.loads(_b64url_decode(header_b64))
    assert header == {"alg": "RS256", "typ": "JWT", "kid": key.kid}

    # Rebuild the public key from the published JWK and verify the signature —
    # this is exactly what Mailcow does.
    jwk = key.public_jwk()
    n = int.from_bytes(_b64url_decode(jwk["n"]), "big")
    e = int.from_bytes(_b64url_decode(jwk["e"]), "big")
    pub = RSAPublicNumbers(e, n).public_key()
    pub.verify(
        _b64url_decode(sig_b64),
        f"{header_b64}.{payload_b64}".encode("ascii"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )  # raises on bad signature
    assert jwk["kid"] == key.kid and jwk["kty"] == "RSA"


def test_signing_key_accepts_single_line_pem_with_escaped_newlines():
    # Operators commonly store the PEM as one env line with literal "\n".
    escaped = _PEM.replace("\n", "\\n")
    key = OIDCSigningKey.from_pem(escaped)
    assert key.sign_jwt({"sub": "x"}).count(".") == 2


def test_signing_key_rejects_weak_or_non_rsa():
    weak = rsa.generate_private_key(public_exponent=65537, key_size=1024)
    pem = weak.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    import pytest

    with pytest.raises(ValueError):
        OIDCSigningKey.from_pem(pem)


# ── dormancy ─────────────────────────────────────────────────────────────────


def test_discovery_and_jwks_dormant_until_configured(client):
    assert client.get("/.well-known/openid-configuration").status_code == 404
    assert client.get("/oidc/jwks").status_code == 404


def test_discovery_and_jwks_live_when_configured(client, monkeypatch):
    _enable_oidc(monkeypatch)
    doc = client.get("/.well-known/openid-configuration")
    assert doc.status_code == 200
    body = doc.json()
    assert body["issuer"] == ISSUER
    assert body["authorization_endpoint"] == f"{ISSUER}/oidc/authorize"
    assert body["id_token_signing_alg_values_supported"] == ["RS256"]
    jwks = client.get("/oidc/jwks").json()
    assert jwks["keys"][0]["kty"] == "RSA"


# ── full flow ────────────────────────────────────────────────────────────────


def test_full_flow_launch_authorize_token_userinfo(client, monkeypatch):
    _enable_oidc(monkeypatch)
    asyncio.run(_seed(slug="of1", email="o@of1.test", mailboxes=("info@acme.test",)))
    _session_login(client, "o@of1.test")

    # 1. Launch: verifies ownership, stashes the mailbox, bounces to Mailcow.
    launch = client.get("/oidc/launch?mailbox=info@acme.test", follow_redirects=False)
    assert launch.status_code == 303
    assert launch.headers["location"] == "https://mail.test/sso"

    # 2. Authorize: mints a single-use code, redirects to the registered callback.
    authz = client.get(
        "/oidc/authorize",
        params={
            "client_id": CLIENT_ID, "redirect_uri": REDIRECT, "response_type": "code",
            "scope": "openid profile email mailcow_template", "state": "xyz", "nonce": "n-123",
        },
        follow_redirects=False,
    )
    assert authz.status_code == 303
    location = authz.headers["location"]
    assert location.startswith(REDIRECT)
    from urllib.parse import parse_qs, urlparse

    qs = parse_qs(urlparse(location).query)
    assert qs["state"] == ["xyz"]
    code = qs["code"][0]

    # 3. Token: client-secret auth → signed id_token asserting the mailbox.
    tok = client.post(
        "/oidc/token",
        data={
            "grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT,
            "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
        },
    )
    assert tok.status_code == 200
    payload = tok.json()
    assert payload["token_type"] == "Bearer" and payload["id_token"]

    claims = json.loads(_b64url_decode(payload["id_token"].split(".")[1]))
    assert claims["email"] == "info@acme.test"
    assert claims["sub"] == "info@acme.test"
    assert claims["aud"] == CLIENT_ID
    assert claims["iss"] == ISSUER
    assert claims["nonce"] == "n-123"

    # 4. UserInfo: bearer access_token → same identity.
    info = client.get(
        "/oidc/userinfo",
        headers={"Authorization": f"Bearer {payload['access_token']}"},
    )
    assert info.status_code == 200
    assert info.json()["email"] == "info@acme.test"


# ── security invariants ──────────────────────────────────────────────────────


def test_authorize_rejects_unregistered_redirect_uri(client, monkeypatch):
    _enable_oidc(monkeypatch)
    asyncio.run(_seed(slug="os1", email="o@os1.test", mailboxes=("info@acme.test",)))
    _session_login(client, "o@os1.test")
    r = client.get(
        "/oidc/authorize",
        params={"client_id": CLIENT_ID, "redirect_uri": "https://evil.test/steal",
                "response_type": "code"},
        follow_redirects=False,
    )
    # Never redirect to an unvalidated URI — return an error instead.
    assert r.status_code == 400
    assert r.json()["error"] == "invalid_request"


def test_authorize_without_launch_denies(client, monkeypatch):
    _enable_oidc(monkeypatch)
    asyncio.run(_seed(slug="os2", email="o@os2.test", mailboxes=("info@acme.test",)))
    _session_login(client, "o@os2.test")
    # No /oidc/launch first → no selected mailbox → access_denied back to callback.
    r = client.get(
        "/oidc/authorize",
        params={"client_id": CLIENT_ID, "redirect_uri": REDIRECT, "response_type": "code"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "error=access_denied" in r.headers["location"]


def test_launch_denies_foreign_mailbox(client, monkeypatch):
    _enable_oidc(monkeypatch)
    asyncio.run(_seed(slug="os3", email="o@os3.test", mailboxes=("info@acme.test",)))
    _session_login(client, "o@os3.test")
    # Foreign mailbox → bounced to /mail, and no selection is stashed, so a
    # follow-up authorize is denied.
    launch = client.get("/oidc/launch?mailbox=x@foreign.test", follow_redirects=False)
    assert launch.headers["location"] == "/mail"
    authz = client.get(
        "/oidc/authorize",
        params={"client_id": CLIENT_ID, "redirect_uri": REDIRECT, "response_type": "code"},
        follow_redirects=False,
    )
    assert "error=access_denied" in authz.headers["location"]


def test_token_rejects_wrong_client_secret(client, monkeypatch):
    _enable_oidc(monkeypatch)
    asyncio.run(_seed(slug="os4", email="o@os4.test", mailboxes=("info@acme.test",)))
    _session_login(client, "o@os4.test")
    client.get("/oidc/launch?mailbox=info@acme.test", follow_redirects=False)
    authz = client.get(
        "/oidc/authorize",
        params={"client_id": CLIENT_ID, "redirect_uri": REDIRECT, "response_type": "code"},
        follow_redirects=False,
    )
    from urllib.parse import parse_qs, urlparse

    code = parse_qs(urlparse(authz.headers["location"]).query)["code"][0]
    r = client.post(
        "/oidc/token",
        data={"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT,
              "client_id": CLIENT_ID, "client_secret": "wrong"},
    )
    assert r.status_code == 401
    assert r.json()["error"] == "invalid_client"


def test_authorization_code_is_single_use(client, monkeypatch):
    _enable_oidc(monkeypatch)
    asyncio.run(_seed(slug="os5", email="o@os5.test", mailboxes=("info@acme.test",)))
    _session_login(client, "o@os5.test")
    client.get("/oidc/launch?mailbox=info@acme.test", follow_redirects=False)
    authz = client.get(
        "/oidc/authorize",
        params={"client_id": CLIENT_ID, "redirect_uri": REDIRECT, "response_type": "code"},
        follow_redirects=False,
    )
    from urllib.parse import parse_qs, urlparse

    code = parse_qs(urlparse(authz.headers["location"]).query)["code"][0]
    data = {"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT,
            "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET}
    assert client.post("/oidc/token", data=data).status_code == 200
    # Replay → rejected (code was burned on first exchange).
    replay = client.post("/oidc/token", data=data)
    assert replay.status_code == 400
    assert replay.json()["error"] == "invalid_grant"
