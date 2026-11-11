from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db_session
from app.models import AdminUser
from app.modules.apps.service import AppsService
from app.modules.dns.service import DnsService
from app.modules.mail.service import MailService
from app.routes import require_admin
from app.services.http import ProviderAPIError
from app.templating import build_templates

templates = build_templates()
router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
async def index(
    request: Request,
    current_admin: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    apps_service = AppsService(request)
    mail_service = MailService(request)
    dns_service = DnsService(request)

    domains = []
    mailboxes = []
    zones = []
    provider_status = []

    apps = await apps_service.list_installed_for_tenant(session, current_admin.tenant_id)
    provider_status.append({"name": "Tetra Engine", "status": "Connected", "detail": f"{len(apps)} apps"})

    try:
        domains, mailboxes = await mail_service.load_for_tenant(session, current_admin.tenant_id)
        detail = "Credentials missing"
        if mail_service.client.is_configured():
            detail = f"{len(domains)} domains · {len(mailboxes)} mailboxes"
        provider_status.append({"name": "Mailcow", "status": "Connected" if mail_service.client.is_configured() else "Not configured", "detail": detail})
    except ProviderAPIError as exc:
        provider_status.append({"name": "Mailcow", "status": "Degraded", "detail": str(exc)})

    try:
        zones, _records, _selected_zone = await dns_service.load_for_tenant(session, current_admin.tenant_id)
        detail = "Token missing"
        if dns_service.client.is_configured():
            detail = f"{len(zones)} DNS zones"
        provider_status.append({"name": "Cloudflare", "status": "Connected" if dns_service.client.is_configured() else "Not configured", "detail": detail})
    except ProviderAPIError as exc:
        provider_status.append({"name": "Cloudflare", "status": "Degraded", "detail": str(exc)})

    admin_count = await session.scalar(
        select(func.count()).select_from(AdminUser).where(AdminUser.tenant_id == current_admin.tenant_id)
    ) or 0
    stats = [
        {"label": "Apps", "value": str(len(apps)), "hint": "Tetra Engine apps"},
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
            "recent_apps": apps[:3],
            "mail_domains": domains[:3],
            "dns_zones": zones[:3],
        },
    )
