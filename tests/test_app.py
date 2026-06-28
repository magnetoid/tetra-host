def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_landing_renders(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Cloud Industry" in r.text


def test_dashboard_requires_auth(client):
    r = client.get("/dashboard", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"].startswith("/auth/login")
    assert r.headers["cache-control"] == "no-store"