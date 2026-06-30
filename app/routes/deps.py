from collections.abc import Awaitable, Callable
from secrets import token_urlsafe
from urllib.parse import quote

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db_session
from app.models import AdminUser
from app.models.admin import ROLE_PLATFORM_ADMIN
from app.models.tenant import TENANT_ACTIVE
from app.modules.auth.service import AuthService


async def get_auth_service(session: AsyncSession = Depends(get_db_session)) -> AuthService:
    return AuthService(session)


def ensure_csrf_token(request: Request) -> str:
    token = request.session.get("csrf_token")
    if token is None:
        token = token_urlsafe(24)
        request.session["csrf_token"] = token
    return token


def verify_csrf_token(request: Request, submitted_token: str) -> None:
    session_token = request.session.get("csrf_token")
    if not submitted_token or not session_token or submitted_token != session_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid CSRF token.")


async def get_current_admin(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> AdminUser | None:
    admin_id = request.session.get("admin_user_id")
    if not admin_id:
        return None
    admin = await auth_service.get_admin_by_id(admin_id)
    if admin is None or not admin.is_active:
        request.session.clear()
        return None
    request.state.current_admin_email = admin.email
    request.state.current_admin_name = admin.full_name
    request.state.current_tenant_id = admin.tenant_id
    request.state.current_tenant_slug = admin.tenant.slug if admin.tenant else None
    request.state.current_tenant_name = admin.tenant.name if admin.tenant else None
    request.state.csrf_token = ensure_csrf_token(request)
    if (
        admin.role != ROLE_PLATFORM_ADMIN
        and request.method in {"POST", "PUT", "PATCH", "DELETE"}
        and not (admin.tenant is not None and admin.tenant.status == TENANT_ACTIVE)
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant is not active.")
    return admin


async def require_admin(
    request: Request,
    current_admin: AdminUser | None = Depends(get_current_admin),
) -> AdminUser:
    if current_admin is not None:
        return current_admin

    destination = quote(str(request.url.path))
    if request.url.query:
        destination = quote(f"{request.url.path}?{request.url.query}")
    raise HTTPException(
        status_code=status.HTTP_303_SEE_OTHER,
        headers={"Location": f"/auth/login?next={destination}"},
    )


async def require_platform_admin(
    request: Request,
    current_admin: AdminUser = Depends(require_admin),
) -> AdminUser:
    if current_admin.role == ROLE_PLATFORM_ADMIN:
        return current_admin
    raise HTTPException(
        status_code=status.HTTP_303_SEE_OTHER,
        headers={"Location": "/dashboard"},
    )


async def require_admin_page(
    request: Request,
    loader: Callable[[], Awaitable[dict[str, object]]],
    current_admin: AdminUser = Depends(require_admin),
) -> dict[str, object]:
    payload = await loader()
    payload["current_admin"] = current_admin
    payload["csrf_token"] = ensure_csrf_token(request)
    return payload
