from fastapi.testclient import TestClient

from app.main import app


def test_health():
    with TestClient(app) as client:
        r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_landing_renders():
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200
    assert "Cloud Industry" in r.text


def test_protected_pages_redirect_to_login_when_logged_out():
    with TestClient(app) as client:
        r = client.get("/dashboard", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/auth/login"
