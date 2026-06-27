from fastapi import APIRouter, Request

from app.services.cloudflare import CloudflareClient
from app.templating import build_templates

templates = build_templates()
router = APIRouter(prefix="/dns", tags=["dns"])


@router.get("")
async def dns_index(request: Request):
    client = CloudflareClient.from_settings()
    zones = await client.list_zones()
    return templates.TemplateResponse(
        request,
        "dns/index.html",
        {
            "zones": zones,
            "cloudflare_configured": client.is_configured(),
        },
    )
