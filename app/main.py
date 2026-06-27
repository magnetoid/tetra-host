from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.db import init_db
from app.modules import load_plugins
from app.plugins import registry
from app.security import parse_session_token
from app.services.tenants import current_user_from_session, ensure_bootstrap_data
from app.templating import build_templates

settings = get_settings()
app = FastAPI(title=settings.app_name)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates: Jinja2Templates = build_templates()

load_plugins()
registry.register_all(app)


@app.on_event("startup")
async def startup() -> None:
    init_db()
    ensure_bootstrap_data(
        admin_email=settings.bootstrap_admin_email,
        admin_password=settings.bootstrap_admin_password,
        tenant_name=settings.bootstrap_tenant_name,
        tenant_slug=settings.bootstrap_tenant_slug,
    )


@app.middleware("http")
async def inject_core_context(request: Request, call_next):
    request.state.settings = settings
    request.state.nav_items = registry.nav_items()
    request.state.plugins = registry.plugins()
    token = request.cookies.get(settings.session_cookie_name)
    session_user = parse_session_token(token) if token else None
    request.state.session_user = session_user
    request.state.current_user = current_user_from_session(session_user)
    return await call_next(request)


@app.get("/health")
async def health():
    return {
        "ok": True,
        "app": settings.app_name,
        "plugins": [p.name for p in registry.nav_items()],
        "theme": settings.theme,
    }
