from fastapi import APIRouter, Request

from app.services.mailcow import MailcowClient
from app.templating import build_templates

templates = build_templates()
router = APIRouter(prefix="/mail", tags=["mail"])


@router.get("")
async def mail_index(request: Request):
    client = MailcowClient.from_settings()
    domains = await client.list_domains()
    return templates.TemplateResponse(
        request,
        "mail/index.html",
        {
            "domains": domains,
            "mailcow_configured": client.is_configured(),
        },
    )
