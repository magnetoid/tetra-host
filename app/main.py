import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from starlette.middleware.sessions import SessionMiddleware

from app.api.graphql import build_graphql_router
from app.api.routes import router as api_router
from app.cache import TTLCache
from app.config import get_settings
from app.csrf import CSRFMiddleware
from app.db import close_db, init_db, session_scope
from app.services.scheduler import start_scheduler, stop_scheduler
from app.modules import load_plugins
from app.modules.auth.service import AuthService
from app.observability import (
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
    configure_logging,
)
from app.plugins import registry
from app.rate_limit import InMemoryRateLimiter
from app.services.http import ProviderAPIError
from app.services.quota import QuotaExceeded
from app.templating import build_templates


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings)
    app.state.cache = TTLCache()
    app.state.rate_limiter = InMemoryRateLimiter()
    app.state.http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(settings.request_timeout_seconds),
        follow_redirects=True,
        headers={"User-Agent": "tetra-host/0.2"},
    )
    await init_db()
    async with session_scope() as session:
        auth_service = AuthService(session)
        await auth_service.ensure_bootstrap_admin(settings)
    app.state.uptime_checks_enabled = settings.uptime_checks_enabled
    if settings.scheduler_enabled:
        start_scheduler(app)
    try:
        yield
    finally:
        if settings.scheduler_enabled:
            await stop_scheduler(app)
        await app.state.http_client.aclose()
        await close_db()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.app_secret,
        session_cookie=settings.session_cookie_name,
        max_age=settings.session_max_age_seconds,
        same_site=settings.session_same_site,
        https_only=settings.session_https_only,
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=5)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    if settings.csrf_protect:
        # Global origin-based CSRF backstop for the browser/session surface. The
        # /api, /graphql, and OIDC-token surfaces (and any Bearer client) are
        # exempt; per-handler token checks remain as defense in depth.
        from urllib.parse import urlsplit

        trusted = set(settings.allowed_hosts)
        base_host = urlsplit(settings.base_url).hostname
        if base_host:
            trusted.add(base_host)
        app.add_middleware(CSRFMiddleware, trusted_hosts=trusted)
    if settings.allowed_hosts and settings.allowed_hosts != ["*"]:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    if settings.force_https_redirect:
        app.add_middleware(HTTPSRedirectMiddleware)

    templates: Jinja2Templates = build_templates()
    app.state.templates = templates

    async def _quota_exceeded_handler(request: Request, exc: QuotaExceeded) -> JSONResponse:
        return JSONResponse(
            status_code=402,
            content={
                # Structured error contract (code/detail/request_id) + legacy keys.
                "code": "quota_exceeded",
                "detail": exc.reason,
                "request_id": getattr(request.state, "request_id", ""),
                "error": exc.error,
                "reason": exc.reason,
                "limit": exc.limit,
                "used": exc.used,
            },
        )

    app.add_exception_handler(QuotaExceeded, _quota_exceeded_handler)

    async def _provider_error_handler(request: Request, exc: ProviderAPIError) -> JSONResponse:
        # Safety net for provider failures not translated by a route: a clean 502
        # instead of a stack-trace 500, with the provider named.
        logging.getLogger("app.providers").error(
            "unhandled provider error from %s: %s", exc.service, exc.message
        )
        return JSONResponse(
            status_code=502,
            content={
                "code": "provider_error",
                "detail": f"{exc.service}: {exc.message}",
                "provider": exc.service,
                "request_id": getattr(request.state, "request_id", ""),
            },
        )

    app.add_exception_handler(ProviderAPIError, _provider_error_handler)

    load_plugins()
    registry.register_all(app)
    app.include_router(api_router)
    # GraphQL surface over the same services (contract-first parity with /api/v1).
    app.include_router(build_graphql_router(), prefix="/graphql")

    @app.middleware("http")
    async def inject_core_context(request: Request, call_next):
        request.state.settings = settings
        session = request.scope.get("session", {})
        # Full nav set (minus public/auth); the template filters platform_admin_only
        # entries by request.state.current_admin_role, which get_current_admin sets
        # authoritatively from the DB on protected routes (session role is the fallback).
        request.state.nav_items = [
            item for item in registry.nav_items() if item.name not in {"public", "auth"}
        ]
        request.state.plugins = registry.plugins()
        request.state.current_admin_email = session.get("admin_email") if isinstance(session, dict) else None
        request.state.current_admin_name = session.get("admin_name") if isinstance(session, dict) else None
        request.state.current_admin_role = session.get("role") if isinstance(session, dict) else None
        request.state.current_tenant_id = session.get("tenant_id") if isinstance(session, dict) else None
        request.state.current_tenant_slug = session.get("tenant_slug") if isinstance(session, dict) else None
        request.state.current_tenant_name = session.get("tenant_name") if isinstance(session, dict) else None
        request.state.csrf_token = session.get("csrf_token", "") if isinstance(session, dict) else ""
        return await call_next(request)

    @app.get("/health")
    async def health():
        # Liveness only — keep it minimal and non-leaky (no plugin/theme/env details).
        return {"ok": True, "app": settings.app_name}

    @app.get("/ready")
    async def ready(response: Response):
        # Readiness = can we serve requests: a real DB round-trip, plus which
        # providers are configured (config presence, not remote pings — a slow
        # third party must not flap our readiness).
        db_ok = True
        try:
            async with session_scope() as db:
                await db.execute(text("SELECT 1"))
        except Exception:
            logging.getLogger(__name__).exception("readiness: database probe failed")
            db_ok = False
        if not db_ok:
            response.status_code = 503
        return {
            "ok": db_ok,
            "database": "up" if db_ok else "down",
            "providers": {
                "coolify": bool(settings.coolify_url and settings.coolify_token),
                "mailcow": bool(settings.mailcow_url and settings.mailcow_api_key),
                "cloudflare": bool(settings.cloudflare_api_token),
            },
        }

    return app


app = create_app()