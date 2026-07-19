"""Optional TOTP two-factor auth — enrollment, login enforcement, and the
guarantee that accounts WITHOUT 2FA are completely unaffected."""

import os
import re
import time

from app.services import totp

ADMIN_EMAIL = os.environ.get("ADMIN_BOOTSTRAP_EMAIL", "admin@example.com")
ADMIN_PASS = os.environ.get("ADMIN_BOOTSTRAP_PASSWORD", "supersecurepassword")


def _current_code(secret: str) -> str:
    return totp._hotp(secret, int(time.time() // totp.PERIOD))


def _api_login(client, **extra):
    return client.post("/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS, **extra})


def _headers(client, **extra) -> dict[str, str]:
    r = _api_login(client, **extra)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _enroll(client) -> tuple[dict[str, str], str, list[str]]:
    """Enable 2FA for the bootstrap admin; return (auth headers, secret, backup codes)."""
    headers = _headers(client)
    setup = client.post("/api/v1/account/2fa/setup", headers=headers).json()
    secret = setup["secret"]
    enable = client.post(
        "/api/v1/account/2fa/enable", headers=headers, json={"code": _current_code(secret)}
    )
    assert enable.status_code == 200, enable.text
    return headers, secret, enable.json()["backup_codes"]


def _csrf(html: str) -> str:
    m = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert m is not None
    return m.group(1)


# --- The safety guarantee: 2FA-off accounts are unchanged --------------------


def test_login_unaffected_when_2fa_disabled(client):
    # API login needs no code.
    assert _api_login(client).status_code == 200
    # Status reports disabled.
    headers = _headers(client)
    status = client.get("/api/v1/account/2fa", headers=headers).json()
    assert status == {"enabled": False, "backup_codes_remaining": 0}
    # Panel login needs no code either.
    page = client.get("/auth/login")
    resp = client.post(
        "/auth/login",
        data={"email": ADMIN_EMAIL, "password": ADMIN_PASS, "csrf_token": _csrf(page.text), "next_url": "/dashboard"},
        follow_redirects=False,
    )
    assert resp.status_code == 303


# --- Enrollment + enforcement -----------------------------------------------


def test_enable_requires_correct_code(client):
    headers = _headers(client)
    client.post("/api/v1/account/2fa/setup", headers=headers)
    bad = client.post("/api/v1/account/2fa/enable", headers=headers, json={"code": "000000"})
    assert bad.status_code == 400
    # Still disabled after a failed enable.
    assert client.get("/api/v1/account/2fa", headers=headers).json()["enabled"] is False


def test_setup_conflicts_once_enabled(client):
    headers, _secret, _codes = _enroll(client)
    conflict = client.post("/api/v1/account/2fa/setup", headers=headers)
    assert conflict.status_code == 409


def test_api_login_requires_code_once_enabled(client):
    _headers_ignored, secret, backup_codes = _enroll(client)

    # No code -> the 2fa_required sentinel.
    missing = _api_login(client)
    assert missing.status_code == 401
    assert missing.json()["detail"] == "2fa_required"

    # Wrong code -> rejected.
    assert _api_login(client, code="000000").status_code == 401

    # Correct TOTP -> success.
    assert _api_login(client, code=_current_code(secret)).status_code == 200

    # A backup code works once, then is consumed.
    assert _api_login(client, code=backup_codes[0]).status_code == 200
    assert _api_login(client, code=backup_codes[0]).status_code == 401
    remaining = client.get(
        "/api/v1/account/2fa", headers={"Authorization": f"Bearer {_api_login(client, code=_current_code(secret)).json()['token']}"}
    ).json()["backup_codes_remaining"]
    assert remaining == len(backup_codes) - 1


def test_panel_login_enforces_2fa(client):
    _headers, secret, _codes = _enroll(client)

    # Password-only -> re-prompt for a code (401, code field now present).
    page = client.get("/auth/login")
    blocked = client.post(
        "/auth/login",
        data={"email": ADMIN_EMAIL, "password": ADMIN_PASS, "csrf_token": _csrf(page.text), "next_url": "/dashboard"},
        follow_redirects=False,
    )
    assert blocked.status_code == 401
    assert 'name="totp_code"' in blocked.text

    # Password + valid TOTP code -> signed in (303 redirect).
    page2 = client.get("/auth/login")
    ok = client.post(
        "/auth/login",
        data={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASS,
            "csrf_token": _csrf(page2.text),
            "next_url": "/dashboard",
            "totp_code": _current_code(secret),
        },
        follow_redirects=False,
    )
    assert ok.status_code == 303


def test_disable_restores_normal_login(client):
    headers, _secret, _codes = _enroll(client)

    # Wrong password refused.
    assert client.post("/api/v1/account/2fa/disable", headers=headers, json={"password": "nope"}).status_code == 400

    # Correct password disables.
    off = client.post("/api/v1/account/2fa/disable", headers=headers, json={"password": ADMIN_PASS})
    assert off.status_code == 204

    # Login no longer needs a code.
    assert _api_login(client).status_code == 200
    assert client.get("/api/v1/account/2fa", headers=_headers(client)).json()["enabled"] is False
