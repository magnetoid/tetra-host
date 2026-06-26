from fastapi import APIRouter, Request
from app.templating import build_templates

from app.services.coolify import CoolifyClient

templates = build_templates()
router = APIRouter(prefix="/sites", tags=["sites"])


@router.get("")
async def list_sites(request: Request):
    sites = CoolifyClient.from_settings().placeholder_sites()
    return templates.TemplateResponse(request, "sites/index.html", {"sites": sites})
