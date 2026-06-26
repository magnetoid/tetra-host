from fastapi import APIRouter, Request
from app.templating import build_templates

templates = build_templates()
router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
async def index(request: Request):
    stats = [
        {"label": "Sites", "value": "0", "hint": "Coolify sync pending"},
        {"label": "Mailboxes", "value": "0", "hint": "Mailcow not connected"},
        {"label": "DNS zones", "value": "0", "hint": "Cloudflare token pending"},
        {"label": "Tenants", "value": "1", "hint": "Cloud Industry admin"},
    ]
    return templates.TemplateResponse(request, "dashboard/index.html", {"stats": stats})
