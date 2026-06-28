from sqlalchemy import func, select

from fastapi import APIRouter, Depends, Request

from app.db import get_db_session
from app.models import AdminUser
from app.modules.dns.service import DnsService
from app.modules.mail.service import MailService
from app.modules.sites.service import SitesService
from app.routes import require_admin
from app.services.http import ProviderAPIError
from app.templating import build_templates

from sqlalchemy.ext.asyncio import AsyncSession

templates = build_templates()
router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
async def index(
    request: Request,
    _: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    sites_service = SitesService(request)
    mail_service = MailService(request)
    dns_service = DnsService(request)

    sites = []
    domains = []
    mailboxes = []
    zones = []
    provider_status = []

    try:
        sites = await sites_service.list_sites()
        detail = "Credentials missing"
        status_label = "Not configured"
        if sites_service.client.is_configured():
            detail = f"{len(sites)} applications"
            status_label = "Connected"
        provider_status.append({"name": "Coolify", "status": status_label, "detail": detail})
    except ProviderAPIError as exc:
        provider_status.append({"name": "Coolify", "status": "Degraded", "detail": str(exc)})

    try:
        domains, mailboxes = await mail_service.load()
        detail = "Credentials missing"
        if mail_service.client.is_configured():
            detail = f"{len(domains)} domains · {len(mailboxes)} mailboxes"
        provider_status.append({"name": "Mailcow", "status": "Connected" if mail_service.client.is_configured() else "Not configured", "detail": detail})
    except ProviderAPIError as exc:
        provider_status.append({"name": "Mailcow", "status": "Degraded", "detail": str(exc)})

    try:
        zones, _records = await dns_service.load()
        detail = "Token missing"
        if dns_service.client.is_configured():
            detail = f"{len(zones)} DNS zones"
        provider_status.append({"name": "Cloudflare", "status": "Connected" if dns_service.client.is_configured() else "Not configured", "detail": detail})
    except ProviderAPIError as exc:
        provider_status.append({"name": "Cloudflare", "status": "Degraded", "detail": str(exc)})

    admin_count = await session.scalar(select(func.count()).select_from(AdminUser)) or 0
    stats = [
        {"label": "Sites", "value": str(len(sites)), "hint": "Coolify application inventory"},
        {"label": "Mailboxes", "value": str(len(mailboxes)), "hint": "Mailcow mailbox count"},
        {"label": "DNS zones", "value": str(len(zones)), "hint": "Cloudflare zone inventory"},
        {"label": "Admins", "value": str(admin_count), "hint": "Authenticated platform operators"},
    ]
    return templates.TemplateResponse(
        request,
        "dashboard/index.html",
        {
            "stats": stats,
            "provider_status": provider_status,
            "recent_sites": sites[:3],
            "mail_domains": domains[:3],
            "dns_zones": zones[:3],
        },
    )