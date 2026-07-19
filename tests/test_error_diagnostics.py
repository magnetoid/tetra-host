"""Runtime-error AI diagnosis: heuristic taxonomy + service + explain endpoint.

Mirrors test_build_diagnostics/test_errors_api. The GlitchTip layer is stubbed by
monkeypatching ErrorsService.get_errors_for_project, so no provider calls happen.
"""

import asyncio

from app.services.error_diagnostics import analyze_error, anthropic_error_diagnoser


def _login_as(client, email: str, password: str) -> dict[str, str]:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['token']}"}


# ── heuristic analyzer ────────────────────────────────────────────────────

def test_analyze_error_null_reference():
    d = analyze_error("TypeError: Cannot read properties of undefined (reading 'id')", "app/user.js", "error")
    assert d.category == "null-reference"
    assert d.source == "heuristic"
    assert d.suggested_fixes
    assert "user.js" in d.summary  # culprit surfaced


def test_analyze_error_connectivity():
    d = analyze_error("OperationalError: could not connect to server", "db/pool.py", "error")
    assert d.category == "connectivity"
    assert d.confidence == "high"  # level=error


def test_analyze_error_missing_module():
    d = analyze_error("ModuleNotFoundError: No module named 'redis'", "worker.py", "fatal")
    assert d.category == "missing-dependency"


def test_analyze_error_unknown_pattern_low_confidence():
    d = analyze_error("SomethingWeird: not a known signature", "", "warning")
    assert d.category == "unknown"
    assert d.confidence == "low"
    assert d.suggested_fixes  # always actionable


def test_anthropic_diagnoser_disabled_without_key():
    # No ANTHROPIC_API_KEY in the test env → the enricher no-ops (caller uses heuristic).
    result = asyncio.run(anthropic_error_diagnoser("TypeError: x", "a.js", "error"))
    assert result is None


# ── explain endpoint (API/CLI/MCP parity surface) ─────────────────────────

_READY = {
    "configured": True,
    "ready": True,
    "project_slug": "web",
    "dsn": "https://x@gt.test/1",
    "issues": [
        {"id": "42", "title": "TypeError: profile.map is not a function", "culprit": "app/x.js",
         "level": "error", "count": 3},
    ],
}

def test_explain_error_requires_auth(client):
    assert client.get("/api/v1/projects/app-x/errors/42/explain").status_code == 401


def test_explain_error_200_with_diagnosis(client, monkeypatch):
    from app.modules.errors.service import ErrorsService

    async def fake_errors(self, session, tenant_id, application_id):
        return _READY

    monkeypatch.setattr(ErrorsService, "get_errors_for_project", fake_errors)
    headers = _login_as(client, "admin@example.com", "supersecurepassword")
    resp = client.get("/api/v1/projects/app-x/errors/42/explain", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["issue_id"] == "42"
    assert body["title"].startswith("TypeError")
    assert body["category"] == "type-error"
    assert body["suggested_fixes"]
    assert body["source"] == "heuristic"  # no ANTHROPIC_API_KEY in tests


def test_explain_error_404_when_issue_missing(client, monkeypatch):
    from app.modules.errors.service import ErrorsService

    async def fake_errors(self, session, tenant_id, application_id):
        return _READY

    monkeypatch.setattr(ErrorsService, "get_errors_for_project", fake_errors)
    headers = _login_as(client, "admin@example.com", "supersecurepassword")
    resp = client.get("/api/v1/projects/app-x/errors/999/explain", headers=headers)
    assert resp.status_code == 404, resp.text


def test_explain_error_404_when_not_ready(client, monkeypatch):
    from app.modules.errors.service import ErrorsService

    async def fake_errors(self, session, tenant_id, application_id):
        return {"configured": False, "ready": False}

    monkeypatch.setattr(ErrorsService, "get_errors_for_project", fake_errors)
    headers = _login_as(client, "admin@example.com", "supersecurepassword")
    resp = client.get("/api/v1/projects/app-x/errors/42/explain", headers=headers)
    assert resp.status_code == 404, resp.text
