from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db_session
from app.models import AdminUser, Tenant, TenantResource
from app.models.tenant import TENANT_ACTIVE, TENANT_SUSPENDED
from app.modules.auth.service import AuthService
from app.routes import require_admin
from app.routes.deps import verify_csrf_token
from app.templating import build_templates

templates = build_templates()
router = APIRouter(prefix="/admin", tags=["admin"])


def _redirect(location: str) -> RedirectResponse:
    return RedirectResponse(location, status_code=status.HTTP_303_SEE_OTHER)


async def _load_tenant_by_slug(session: AsyncSession, slug: str) -> Tenant | None:
    auth_service = AuthService(session)
    return await auth_service.get_tenant_by_slug(slug)


async def _load_admin_page_data(request: Request, session: AsyncSession, current_admin: AdminUser) -> dict[str, object]:
    admins = list(
        (
            await session.scalars(
                select(AdminUser)
                .options(selectinload(AdminUser.tenant))
                .order_by(AdminUser.created_at)
            )
        ).all()
    )
    tenants = list((await session.scalars(select(Tenant).order_by(Tenant.created_at))).all())
    resources = list(
        (
            await session.scalars(
                select(TenantResource)
                .options(selectinload(TenantResource.tenant))
                .order_by(TenantResource.created_at)
            )
        ).all()
    )
    platform_checks = [
        {
            "name": "Coolify",
            "configured": bool(request.state.settings.coolify_url and request.state.settings.coolify_token),
            "detail": request.state.settings.coolify_url or "Missing URL and token",
        },
        {
            "name": "Mailcow",
            "configured": bool(request.state.settings.mailcow_url and request.state.settings.mailcow_api_key),
            "detail": request.state.settings.mailcow_url or "Missing URL and API key",
        },
        {
            "name": "Cloudflare",
            "configured": bool(request.state.settings.cloudflare_api_token),
            "detail": "Scoped token present" if request.state.settings.cloudflare_api_token else "Missing API token",
        },
    ]
    return {
        "admins": admins,
        "tenants": tenants,
        "resources": resources,
        "tenant_name": current_admin.tenant.name if current_admin.tenant else "",
        "platform_checks": platform_checks,
        "provider_options": ["coolify", "mailcow", "cloudflare"],
        "resource_type_options": ["site", "database", "server", "mail_domain", "mailbox", "dns_zone", "dns_record"],
        "error": request.query_params.get("error"),
        "success": request.query_params.get("success"),
        "csrf_token": request.state.csrf_token,
    }


@router.get("")
async def admin_index(
    request: Request,
    current_admin: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    payload = await _load_admin_page_data(request, session, current_admin)
    return templates.TemplateResponse(request, "admin/index.html", payload)


@router.post("/tenants")
async def create_tenant(
    request: Request,
    name: str = Form(...),
    slug: str = Form(...),
    csrf_token: str = Form(...),
    _: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    verify_csrf_token(request, csrf_token)
    auth_service = AuthService(session)
    normalized_slug = auth_service.normalize_slug(slug)
    existing = await auth_service.get_tenant_by_slug(normalized_slug)
    if existing is not None:
        return _redirect("/admin?error=Tenant+slug+already+exists")

    tenant = Tenant(name=name.strip(), slug=normalized_slug, status=TENANT_ACTIVE)
    session.add(tenant)
    await session.flush()
    return _redirect("/admin?success=Tenant+created")


@router.post("/tenants/{tenant_slug}/activate")
async def activate_tenant(
    request: Request,
    tenant_slug: str,
    csrf_token: str = Form(...),
    _: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    verify_csrf_token(request, csrf_token)
    tenant = await _load_tenant_by_slug(session, tenant_slug)
    if tenant is None:
        return _redirect("/admin?error=Tenant+not+found")
    tenant.status = TENANT_ACTIVE
    await session.flush()
    return _redirect("/admin?success=Tenant+activated")


@router.post("/tenants/{tenant_slug}/deactivate")
async def deactivate_tenant(
    request: Request,
    tenant_slug: str,
    csrf_token: str = Form(...),
    _: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    verify_csrf_token(request, csrf_token)
    tenant = await _load_tenant_by_slug(session, tenant_slug)
    if tenant is None:
        return _redirect("/admin?error=Tenant+not+found")
    tenant.status = TENANT_SUSPENDED
    await session.flush()
    return _redirect("/admin?success=Tenant+deactivated")


@router.post("/admins")
async def create_tenant_admin(
    request: Request,
    tenant_slug: str = Form(...),
    email: str = Form(...),
    full_name: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
    _: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    verify_csrf_token(request, csrf_token)
    auth_service = AuthService(session)
    tenant = await auth_service.get_tenant_by_slug(tenant_slug)
    if tenant is None:
        return _redirect("/admin?error=Tenant+not+found")

    normalized_email = auth_service.normalize_email(email)
    existing_admin = await auth_service.get_admin_by_email(normalized_email)
    if existing_admin is not None:
        return _redirect("/admin?error=Admin+email+already+exists")

    admin = AdminUser(
        tenant_id=tenant.id,
        email=normalized_email,
        full_name=full_name.strip(),
        password_hash=auth_service.hash_password(password),
        is_active=True,
    )
    session.add(admin)
    await session.flush()
    return _redirect("/admin?success=Tenant+admin+created")


@router.post("/resources")
async def create_tenant_resource(
    request: Request,
    tenant_slug: str = Form(...),
    provider: str = Form(...),
    resource_type: str = Form(...),
    external_id: str = Form(...),
    display_name: str = Form(...),
    csrf_token: str = Form(...),
    _: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    verify_csrf_token(request, csrf_token)
    auth_service = AuthService(session)
    tenant = await auth_service.get_tenant_by_slug(tenant_slug)
    if tenant is None:
        return _redirect("/admin?error=Tenant+not+found")

    normalized_provider = provider.strip().lower()
    normalized_resource_type = resource_type.strip().lower()
    normalized_external_id = external_id.strip()
    existing = await session.scalar(
        select(TenantResource).where(
            TenantResource.provider == normalized_provider,
            TenantResource.resource_type == normalized_resource_type,
            TenantResource.external_id == normalized_external_id,
        )
    )
    if existing is not None:
        return _redirect("/admin?error=Resource+already+assigned")

    resource = TenantResource(
        tenant_id=tenant.id,
        provider=normalized_provider,
        resource_type=normalized_resource_type,
        external_id=normalized_external_id,
        display_name=display_name.strip() or normalized_external_id,
    )
    session.add(resource)
    await session.flush()
    return _redirect("/admin?success=Resource+assigned")

@router.post("/resources/{resource_id}/delete")
async def delete_tenant_resource(
    request: Request,
    resource_id: str,
    csrf_token: str = Form(...),
    _: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    verify_csrf_token(request, csrf_token)
    resource = await session.get(TenantResource, resource_id)
    if resource is None:
        return _redirect("/admin?error=Resource+assignment+not+found")
    await session.delete(resource)
    await session.flush()
    return _redirect("/admin?success=Resource+assignment+removed")
