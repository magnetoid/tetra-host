from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db_session
from app.models import AdminUser
from app.modules.mail.service import MailService
from app.routes import require_admin
from app.services.http import ProviderAPIError
from app.templating import build_templates

templates = build_templates()
router = APIRouter(prefix="/mail", tags=["mail"])


@router.get("")
async def mail_index(
    request: Request,
    current_admin: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    refresh = request.query_params.get("refresh") == "1"
    service = MailService(request)
    domains = []
    mailboxes = []
    error = None
    try:
        domains, mailboxes = await service.load_for_tenant(session, current_admin.tenant_id, refresh=refresh)
    except ProviderAPIError as exc:
        error = str(exc)
    return templates.TemplateResponse(
        request,
        "mail/index.html",
        {
            "domains": domains,
            "mailboxes": mailboxes[:10],
            "error": error,
            "provider_configured": service.client.is_configured(),
        },
    )