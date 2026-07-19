"""/api/v1/account/notifications — outbound webhook channel CRUD + test send."""

import os

ADMIN_EMAIL = os.environ.get("ADMIN_BOOTSTRAP_EMAIL", "admin@example.com")
ADMIN_PASS = os.environ.get("ADMIN_BOOTSTRAP_PASSWORD", "supersecurepassword")


def _headers(client) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_requires_auth(client):
    assert client.get("/api/v1/account/notifications").status_code == 401


def test_create_list_delete_flow(client):
    headers = _headers(client)

    # Create — secret returned once, event normalized.
    created = client.post(
        "/api/v1/account/notifications",
        headers=headers,
        json={"name": "Slack", "url": "https://hooks.example.com/abc", "events": "*"},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["secret"].startswith("whsec_")
    assert body["name"] == "Slack"
    channel_id = body["id"]

    # List — no secret field leaks.
    listed = client.get("/api/v1/account/notifications", headers=headers).json()
    assert len(listed) == 1
    assert "secret" not in listed[0]
    assert listed[0]["id"] == channel_id

    # Delete.
    assert client.delete(f"/api/v1/account/notifications/{channel_id}", headers=headers).status_code == 200
    assert client.get("/api/v1/account/notifications", headers=headers).json() == []
    # Deleting again -> 404.
    assert client.delete(f"/api/v1/account/notifications/{channel_id}", headers=headers).status_code == 404


def test_rejects_non_http_url(client):
    headers = _headers(client)
    bad = client.post(
        "/api/v1/account/notifications",
        headers=headers,
        json={"name": "x", "url": "ftp://nope"},
    )
    assert bad.status_code == 400


def test_test_endpoint_reports_delivery_result(client):
    headers = _headers(client)
    # An unroutable target so delivery deterministically fails (no external network).
    created = client.post(
        "/api/v1/account/notifications",
        headers=headers,
        json={"name": "dead", "url": "http://127.0.0.1:9/hook"},
    ).json()
    result = client.post(
        f"/api/v1/account/notifications/{created['id']}/test", headers=headers
    )
    assert result.status_code == 200
    payload = result.json()
    assert payload["ok"] is False
    assert payload["status"]  # a human-readable label ("unreachable" / "http …")

    # 404 for an unknown channel.
    assert client.post("/api/v1/account/notifications/nope/test", headers=headers).status_code == 404
