from fastapi import APIRouter, Request
from app.templating import build_templates

templates = build_templates()
router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("")
async def admin_index(request: Request):
    tenants = [{"name": "Cloud Industry", "plan": "Admin", "sites": 0}]
    return templates.TemplateResponse(request, "admin/index.html", {"tenants": tenants})
