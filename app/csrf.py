"""Origin-based CSRF defense for the session-cookie (browser) surface.

Every state-changing form POST in the panel already verifies a per-session CSRF
token in its handler (``verify_csrf_token`` in ``app/routes/deps.py``). This
middleware is a *global backstop*: it rejects cross-site unsafe requests before
they reach a handler, so a handler that forgets its token check is still
protected against the classic CSRF vector — a malicious page auto-submitting a
form to our origin using the victim's session cookie.

Design choices that make it safe to bolt on:

* **Header-only.** It never reads the request body, so it cannot interfere with
  form parsing, file uploads, or streaming. (Reading the body in middleware is a
  well-known Starlette footgun that empties the stream for the handler.)
* **Programmatic surfaces are exempt.** Anything under ``/api/`` or ``/graphql``,
  the OIDC ``/oidc/token`` endpoint, and any request carrying an
  ``Authorization`` header (Bearer clients — the console, the ``tetra`` CLI, the
  MCP server; the HMAC-signed GitHub webhook lives under ``/api/``) authenticate
  without cookies and are not CSRF-exposed.
* **Never weakens the status quo.** Detection uses ``Sec-Fetch-Site`` (sent by
  all current browsers) with an ``Origin`` host fallback. When neither signal is
  present — a non-browser client, or a browser old enough to omit both — the
  request is allowed through and the handler's token check remains the backstop.
  We only *add* protection.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
# Cookie-less, programmatic surfaces. Bearer clients are also caught by the
# Authorization-header check below; these prefixes cover cookie-less POSTs that
# authenticate by other means (HMAC webhook signature, OIDC client secret).
EXEMPT_PREFIXES = ("/api/", "/graphql", "/oidc/token")
# Sec-Fetch-Site values that are NOT a cross-site request.
SAFE_FETCH_SITES = frozenset({"same-origin", "same-site", "none"})


class CSRFMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, trusted_hosts: set[str] | None = None) -> None:
        super().__init__(app)
        self._trusted_hosts = {h.lower() for h in (trusted_hosts or set()) if h}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if self._is_exempt(request):
            return await call_next(request)
        if not self._is_same_origin(request):
            return _reject(request)
        return await call_next(request)

    def _is_exempt(self, request: Request) -> bool:
        if request.method in SAFE_METHODS:
            return True
        if request.headers.get("authorization"):
            return True
        path = request.url.path
        return any(path.startswith(prefix) for prefix in EXEMPT_PREFIXES)

    def _is_same_origin(self, request: Request) -> bool:
        fetch_site = request.headers.get("sec-fetch-site")
        if fetch_site:
            return fetch_site in SAFE_FETCH_SITES
        origin = request.headers.get("origin")
        if origin:
            host = (urlsplit(origin).hostname or "").lower()
            return host in self._allowed_hosts(request)
        # No browser signal at all → defer to the handler's CSRF-token check.
        return True

    def _allowed_hosts(self, request: Request) -> set[str]:
        hosts = set(self._trusted_hosts)
        request_host = (request.headers.get("host") or "").split(":", 1)[0].lower()
        if request_host:
            hosts.add(request_host)
        return hosts


def _reject(request: Request) -> Response:
    return JSONResponse(
        status_code=403,
        content={
            "code": "csrf_failed",
            "detail": "Cross-site request blocked.",
            "request_id": getattr(request.state, "request_id", ""),
        },
    )
