import asyncio

from fastapi import APIRouter, Request

from app.dependencies import require_login
from app.services.cloudflare import CloudflareClient
from app.services.coolify import CoolifyClient
from app.services.mailcow import MailcowClient
from app.services.tenants import get_tenant_summaries
from app.templating import build_templates

templates = build_templates()
router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
async def index(request: Request):
    redirect = await require_login(request)
    if redirect:
        return redirect

    coolify_client = CoolifyClient.from_settings()
    mail_client = MailcowClient.from_settings()
    dns_client = CloudflareClient.from_settings()
    apps, domains, zones = await asyncio.gather(
        coolify_client.list_applications(),
        mail_client.list_domains(),
        dns_client.list_zones(),
    )
    tenant_count = len(get_tenant_summaries())
    stats = [
        {"label": "Sites", "value": str(len(apps)), "hint": "Coolify projects synced"},
        {"label": "Mail domains", "value": str(len(domains)), "hint": "Mailcow domains visible"},
        {"label": "DNS zones", "value": str(len(zones)), "hint": "Cloudflare zones available"},
        {"label": "Tenants", "value": str(tenant_count), "hint": "Customer tenant records"},
    ]
    return templates.TemplateResponse(
        request,
        "dashboard/index.html",
        {
            "stats": stats,
            "current_user": request.state.current_user,
        },
    )
