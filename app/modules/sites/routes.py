from fastapi import APIRouter, Request

from app.services.coolify import CoolifyClient
from app.templating import build_templates

templates = build_templates()
router = APIRouter(prefix="/sites", tags=["sites"])


@router.get("")
async def list_sites(request: Request):
    sites = await CoolifyClient.from_settings().list_applications()
    return templates.TemplateResponse(request, "sites/index.html", {"sites": sites})
