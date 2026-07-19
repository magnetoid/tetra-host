"""/api/v1/account/monitors — uptime monitor CRUD + on-demand check."""

import os

ADMIN_EMAIL = os.environ.get("ADMIN_BOOTSTRAP_EMAIL", "admin@example.com")
ADMIN_PASS = os.environ.get("ADMIN_BOOTSTRAP_PASSWORD", "supersecurepassword")


def _headers(client) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_requires_auth(client):
    assert client.get("/api/v1/account/monitors").status_code == 401


def test_create_list_delete(client):
    headers = _headers(client)
    created = client.post(
        "/api/v1/account/monitors",
        headers=headers,
        json={"name": "site", "url": "https://example.com"},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["status"] == "unknown"
    monitor_id = body["id"]

    listed = client.get("/api/v1/account/monitors", headers=headers).json()
    assert len(listed) == 1 and listed[0]["id"] == monitor_id

    assert client.delete(f"/api/v1/account/monitors/{monitor_id}", headers=headers).status_code == 200
    assert client.get("/api/v1/account/monitors", headers=headers).json() == []
    assert client.delete(f"/api/v1/account/monitors/{monitor_id}", headers=headers).status_code == 404


def test_rejects_non_http_url(client):
    headers = _headers(client)
    assert client.post(
        "/api/v1/account/monitors", headers=headers, json={"name": "x", "url": "tcp://nope"}
    ).status_code == 400


def test_manual_check_updates_status(client):
    headers = _headers(client)
    # Unroutable target → the probe deterministically records "down".
    created = client.post(
        "/api/v1/account/monitors",
        headers=headers,
        json={"name": "dead", "url": "http://127.0.0.1:9/"},
    ).json()
    checked = client.post(f"/api/v1/account/monitors/{created['id']}/check", headers=headers)
    assert checked.status_code == 200
    assert checked.json()["status"] == "down"
    assert checked.json()["last_detail"]

    assert client.post("/api/v1/account/monitors/nope/check", headers=headers).status_code == 404
