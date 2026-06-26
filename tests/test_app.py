from fastapi.testclient import TestClient

from app.main import app


def test_health():
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_landing_renders():
    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200
    assert "Cloud Industry" in r.text
