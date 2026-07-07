"""Account — the signed-in admin's own profile/settings surface.

Reached from the upper-right account dropdown, not the sidebar (empty nav_href).
Any admin may view and edit their own account (profile + password); state-changing
posts are CSRF-protected and scoped to `current_admin` — never another admin.
"""

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db_session
from app.models import AdminUser
from app.models.admin import ROLE_PLATFORM_ADMIN
from app.modules.auth.service import AuthService
from app.routes.deps import require_admin, verify_csrf_token
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


@router.post("/profile")
async def update_profile(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    csrf_token: str = Form(...),
    current_admin: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    verify_csrf_token(request, csrf_token)
    try:
        admin = await AuthService(session).update_profile(
            current_admin, full_name=full_name, email=email
        )
    except ValueError as exc:
        return RedirectResponse(f"/account?profile_error={exc}", status_code=status.HTTP_303_SEE_OTHER)
    # keep the session-rendered identity (topbar/nav) in sync with the new values
    request.session["admin_email"] = admin.email
    request.session["admin_name"] = admin.full_name
    return RedirectResponse("/account?profile=updated", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/password")
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    csrf_token: str = Form(...),
    current_admin: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    verify_csrf_token(request, csrf_token)
    if new_password != confirm_password:
        return RedirectResponse(
            "/account?password_error=New passwords do not match.",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    try:
        await AuthService(session).change_password(
            current_admin, current_password=current_password, new_password=new_password
        )
    except ValueError as exc:
        return RedirectResponse(f"/account?password_error={exc}", status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse("/account?password=changed", status_code=status.HTTP_303_SEE_OTHER)
