def test_ready_exposes_provider_configuration_flags(client):
    data = client.get("/ready").json()
    assert data["ok"] is True
    assert "mailcow" in data["providers"]
    # Coolify is an import source now, not a provider the panel manages.
    assert "coolify" not in data["providers"]


def test_coolify_pages_are_gone(client):
    for path in ("/projects", "/servers", "/databases", "/maintenance"):
        assert client.get(path, follow_redirects=False).status_code == 404, path


def test_dashboard_renders_operational_copy_for_authenticated_admin(authenticated_client):
    html = authenticated_client.get("/dashboard").text
    assert "PaaS Overview" in html
    assert "Provider connectivity" in html
    assert "Refresh providers" in html
    assert "Tetra Engine" in html
    assert "Coolify" not in html
