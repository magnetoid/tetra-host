"""Account — the signed-in admin's own profile/settings surface.

Reached from the upper-right account dropdown, not the sidebar (empty nav_href).
Slice A ships a read-only profile; change-password + notification preferences land
in the account settings slice. Any admin may view their own account.
"""

from fastapi import APIRouter, Depends, Request

from app.models import AdminUser
from app.models.admin import ROLE_PLATFORM_ADMIN
from app.routes.deps import require_admin
from app.templating import build_templates

templates = build_templates()
router = APIRouter(prefix="/account", tags=["account"])


@router.get("")
async def account_page(
    request: Request,
    current_admin: AdminUser = Depends(require_admin),
):
    tenant = current_admin.tenant
    return templates.TemplateResponse(
        request,
        "account/index.html",
        {
            "admin": current_admin,
            "is_platform_admin": current_admin.role == ROLE_PLATFORM_ADMIN,
            "tenant_name": tenant.name if tenant else "",
        },
    )
