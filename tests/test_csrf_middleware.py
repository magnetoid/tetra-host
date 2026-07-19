"""Origin-based CSRF backstop (app/csrf.py).

The middleware blocks cross-site unsafe requests to the browser/session surface
without reading the body, while leaving programmatic (Bearer/API) surfaces and
signal-less clients untouched (the per-handler token check remains the backstop
for those). These tests drive it through the real app via TestClient by setting
the browser fetch-metadata headers a real cross-site attack would carry.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def _post(client: TestClient, path: str, **headers: str):
    # Unauthenticated POST is fine: the middleware runs before auth, so a blocked
    # request never reaches the handler. We assert on the middleware's verdict.
    return client.post(path, data={"x": "1"}, headers=headers, follow_redirects=False)


def test_cross_site_post_is_blocked(client: TestClient) -> None:
    resp = _post(client, "/auth/login", **{"sec-fetch-site": "cross-site"})
    assert resp.status_code == 403
    assert resp.json()["code"] == "csrf_failed"


def test_cross_site_via_foreign_origin_is_blocked(client: TestClient) -> None:
    # No Sec-Fetch-Site, but a foreign Origin host → blocked.
    resp = _post(client, "/auth/login", origin="https://evil.example.com")
    assert resp.status_code == 403
    assert resp.json()["code"] == "csrf_failed"


def test_same_origin_fetch_site_passes(client: TestClient) -> None:
    # same-origin signal → allowed through to the handler (which then does its
    # own token check; a 400/422/303 here means it passed the CSRF gate).
    resp = _post(client, "/auth/login", **{"sec-fetch-site": "same-origin"})
    assert resp.status_code != 403


def test_same_origin_via_matching_origin_passes(client: TestClient) -> None:
    resp = _post(client, "/auth/login", origin="http://testserver")
    assert resp.status_code != 403


def test_no_browser_signal_defers_to_handler(client: TestClient) -> None:
    # No fetch-metadata and no Origin (the TestClient default) → allowed; the
    # handler's own CSRF-token check is the backstop. Must not 403.
    resp = _post(client, "/auth/login")
    assert resp.status_code != 403


def test_api_surface_is_exempt(client: TestClient) -> None:
    # /api/* is cookie-less (Bearer) and must never be CSRF-blocked even with a
    # cross-site signal. Unauthorized (401) is fine; 403 csrf_failed is not.
    resp = client.post(
        "/api/v1/projects",
        json={},
        headers={"sec-fetch-site": "cross-site"},
        follow_redirects=False,
    )
    assert resp.status_code != 403 or resp.json().get("code") != "csrf_failed"


def test_bearer_request_is_exempt(client: TestClient) -> None:
    # An Authorization header marks a programmatic client → exempt.
    resp = _post(
        client,
        "/auth/login",
        **{"sec-fetch-site": "cross-site", "authorization": "Bearer sometoken"},
    )
    assert resp.status_code != 403


def test_safe_methods_pass(client: TestClient) -> None:
    resp = client.get("/auth/login", headers={"sec-fetch-site": "cross-site"})
    assert resp.status_code == 200
