from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.modules import load_plugins
from app.plugins import registry
from app.templating import build_templates

settings = get_settings()
app = FastAPI(title=settings.app_name)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates: Jinja2Templates = build_templates()

load_plugins()
registry.register_all(app)


@app.middleware("http")
async def inject_core_context(request: Request, call_next):
    request.state.settings = settings
    request.state.nav_items = registry.nav_items()
    request.state.plugins = registry.plugins()
    return await call_next(request)


@app.get("/health")
async def health():
    return {
        "ok": True,
        "app": settings.app_name,
        "plugins": [p.name for p in registry.nav_items()],
        "theme": settings.theme,
    }
