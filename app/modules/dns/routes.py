from fastapi import APIRouter, Request
from app.templating import build_templates

templates = build_templates()
router = APIRouter(prefix="/dns", tags=["dns"])


@router.get("")
async def dns_index(request: Request):
    zones = []
    return templates.TemplateResponse(request, "dns/index.html", {"zones": zones})
