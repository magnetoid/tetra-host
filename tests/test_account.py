"""Account self-service — /api/v1/account (profile + change-password)."""

import re


def _extract_csrf(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match is not None
    return match.group(1)


def _token(client, email="admin@example.com", password="supersecurepassword") -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _auth(client, **kw) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(client, **kw)}"}


def test_account_update_profile(client):
    headers = _auth(client)
    r = client.patch(
        "/api/v1/account", headers=headers,
        json={"full_name": "Renamed Admin", "email": "renamed@example.com"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["full_name"] == "Renamed Admin"
    assert body["email"] == "renamed@example.com"
    # persisted — /auth/me reflects it
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.json()["email"] == "renamed@example.com"


def test_account_update_rejects_blank_name(client):
    r = client.patch(
        "/api/v1/account", headers=_auth(client),
        json={"full_name": "   ", "email": "admin@example.com"},
    )
    assert r.status_code == 400
    assert "Name" in r.json()["detail"]


def test_account_change_password_flow(client):
    headers = _auth(client)
    # wrong current → 400
    assert client.post(
        "/api/v1/account/password", headers=headers,
        json={"current_password": "wrong", "new_password": "brandnewsecret1"},
    ).status_code == 400
    # weak new → 400
    assert client.post(
        "/api/v1/account/password", headers=headers,
        json={"current_password": "supersecurepassword", "new_password": "short"},
    ).status_code == 400
    # same as current → 400
    assert client.post(
        "/api/v1/account/password", headers=headers,
        json={"current_password": "supersecurepassword", "new_password": "supersecurepassword"},
    ).status_code == 400
    # valid rotation → 200, and the new password logs in while the old one does not
    ok = client.post(
        "/api/v1/account/password", headers=headers,
        json={"current_password": "supersecurepassword", "new_password": "brandnewsecret1"},
    )
    assert ok.status_code == 200 and ok.json() == {"ok": True}
    assert client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com", "password": "supersecurepassword"},
    ).status_code == 401
    assert client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com", "password": "brandnewsecret1"},
    ).status_code == 200


def test_account_requires_auth(client):
    assert client.patch("/api/v1/account", json={"full_name": "x", "email": "x@y.z"}).status_code == 401
    assert client.post(
        "/api/v1/account/password", json={"current_password": "a", "new_password": "b"},
    ).status_code == 401


# ── Panel (session-cookie) surface ──────────────────────────────────────────
def test_panel_account_renders_forms(authenticated_client):
    html = authenticated_client.get("/account").text
    assert 'action="/account/profile"' in html
    assert 'action="/account/password"' in html


def test_panel_account_profile_update(authenticated_client):
    csrf = _extract_csrf(authenticated_client.get("/account").text)
    r = authenticated_client.post(
        "/account/profile",
        data={"full_name": "Panel Renamed", "email": "panel@example.com", "csrf_token": csrf},
        follow_redirects=False,
    )
    assert r.status_code == 303 and r.headers["location"] == "/account?profile=updated"
    assert "panel@example.com" in authenticated_client.get("/account").text


def test_panel_account_password_change_and_mismatch(authenticated_client):
    csrf = _extract_csrf(authenticated_client.get("/account").text)
    # mismatch → redirected back with an error, password unchanged
    mism = authenticated_client.post(
        "/account/password",
        data={"current_password": "supersecurepassword", "new_password": "brandnewsecret1",
              "confirm_password": "different1234", "csrf_token": csrf},
        follow_redirects=False,
    )
    assert mism.status_code == 303 and "password_error" in mism.headers["location"]
    # valid change → success redirect
    ok = authenticated_client.post(
        "/account/password",
        data={"current_password": "supersecurepassword", "new_password": "brandnewsecret1",
              "confirm_password": "brandnewsecret1", "csrf_token": csrf},
        follow_redirects=False,
    )
    assert ok.status_code == 303 and ok.headers["location"] == "/account?password=changed"


def test_panel_account_profile_rejects_missing_csrf(authenticated_client):
    r = authenticated_client.post(
        "/account/profile",
        data={"full_name": "No CSRF", "email": "nocsrf@example.com", "csrf_token": "bogus"},
        follow_redirects=False,
    )
    assert r.status_code in (400, 403)
