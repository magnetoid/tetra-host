from fastapi import APIRouter, Request
from app.templating import build_templates

templates = build_templates()
router = APIRouter(prefix="/mail", tags=["mail"])


@router.get("")
async def mail_index(request: Request):
    domains = []
    return templates.TemplateResponse(request, "mail/index.html", {"domains": domains})
