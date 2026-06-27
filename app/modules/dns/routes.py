from fastapi import APIRouter, Request

from app.dependencies import require_login
from app.services.cloudflare import CloudflareClient
from app.templating import build_templates

templates = build_templates()
router = APIRouter(prefix="/dns", tags=["dns"])


@router.get("")
async def dns_index(request: Request):
    redirect = await require_login(request)
    if redirect:
        return redirect
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


@router.get("/{zone_id}")
async def dns_zone_detail(request: Request, zone_id: str):
    redirect = await require_login(request)
    if redirect:
        return redirect
    client = CloudflareClient.from_settings()
    zones = await client.list_zones()
    zone = next((z for z in zones if z.id == zone_id), None)
    records = await client.list_records(zone_id)
    return templates.TemplateResponse(
        request,
        "dns/index.html",
        {
            "zones": zones,
            "selected_zone": zone,
            "records": records,
            "cloudflare_configured": client.is_configured(),
        },
    )
