from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.api.routes import router as api_router
from app.cache import TTLCache
from app.config import get_settings
from app.db import close_db, init_db, session_scope
from app.modules import load_plugins
from app.modules.auth.service import AuthService
from app.observability import (
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
    configure_logging,
)
from app.plugins import registry
from app.rate_limit import InMemoryRateLimiter
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
    try:
        yield
    finally:
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
                "error": exc.error,
                "reason": exc.reason,
                "limit": exc.limit,
                "used": exc.used,
            },
        )

    app.add_exception_handler(QuotaExceeded, _quota_exceeded_handler)

    load_plugins()
    registry.register_all(app)
    app.include_router(api_router)

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
        return {
            "ok": True,
            "app": settings.app_name,
            "plugins": [p.name for p in registry.nav_items()],
            "theme": settings.theme,
            "env": settings.app_env,
        }

    @app.get("/ready")
    async def ready():
        return {
            "ok": True,
            "database_url": settings.database_url.split("://", 1)[0],
            "providers": {
                "coolify": bool(settings.coolify_url and settings.coolify_token),
                "mailcow": bool(settings.mailcow_url and settings.mailcow_api_key),
                "cloudflare": bool(settings.cloudflare_api_token),
            },
        }

    return app


app = create_app()