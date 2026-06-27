from fastapi import APIRouter, Request

from app.dependencies import require_login
from app.services.tenants import get_tenant_summaries
from app.templating import build_templates

templates = build_templates()
router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("")
async def admin_index(request: Request):
    redirect = await require_login(request)
    if redirect:
        return redirect
    tenants = get_tenant_summaries()
    return templates.TemplateResponse(
        request,
        "admin/index.html",
        {
            "tenants": tenants,
            "current_user": request.state.current_user,
        },
    )
