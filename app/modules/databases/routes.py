from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db_session
from app.models import AdminUser
from app.models.tenant_resource import PROVIDER_COOLIFY, RESOURCE_TYPE_DATABASE
from app.routes.deps import require_admin, verify_csrf_token
from app.services.coolify import CoolifyClient
from app.services.http import ProviderAPIError
from app.services.tenant_resources import TenantResourceFilter
from app.templating import build_templates

templates = build_templates()
router = APIRouter(prefix="/databases", tags=["databases"])


def _get_client(request: Request) -> CoolifyClient:
    return CoolifyClient.from_settings(
        http_client=request.app.state.http_client,
        cache=request.app.state.cache,
    )


async def _ensure_db_access(session: AsyncSession, tenant_id: str | None, db_id: str) -> None:
    allowed = await TenantResourceFilter(session, tenant_id).is_resource_accessible(
        provider=PROVIDER_COOLIFY, resource_type=RESOURCE_TYPE_DATABASE, external_id=db_id
    )
    if not allowed:
        raise ProviderAPIError(service="Coolify", message="Database is not assigned to this tenant.", status_code=403)


@router.get("")
async def list_databases(
    request: Request,
    current_admin: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    client = _get_client(request)
    databases = []
    error = None
    query = request.query_params.get("q", "").strip().lower()
    try:
        databases = await client.list_databases()
        databases = await TenantResourceFilter(session, current_admin.tenant_id).filter_databases(databases)
        if query:
            databases = [d for d in databases if query in d.name.lower() or query in d.type.lower() or query in d.status.lower()]
    except ProviderAPIError as exc:
        error = str(exc)
    return templates.TemplateResponse(
        request,
        "databases/index.html",
        {
            "databases": databases,
            "error": error,
            "q": request.query_params.get("q", ""),
            "actions_enabled": request.state.settings.enable_provider_actions and client.is_configured(),
        },
    )


async def _run_db_action(request: Request, session: AsyncSession, tenant_id: str | None, db_id: str, action: str) -> RedirectResponse:
    if not request.state.settings.enable_provider_actions:
        return RedirectResponse(f"/databases?{action}=disabled", status_code=status.HTTP_303_SEE_OTHER)
    client = _get_client(request)
    try:
        await _ensure_db_access(session, tenant_id, db_id)
        method = getattr(client, f"{action}_database")
        result = await method(db_id)
        message = result.get("message", f"Database {action} requested.")
        return RedirectResponse(f"/databases?{action}={message}", status_code=status.HTTP_303_SEE_OTHER)
    except ProviderAPIError as exc:
        return RedirectResponse(f"/databases?{action}_error={str(exc)}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{db_id}/start")
async def start_database(request: Request, db_id: str, csrf_token: str = Form(...), current_admin: AdminUser = Depends(require_admin), session: AsyncSession = Depends(get_db_session)):
    verify_csrf_token(request, csrf_token)
    return await _run_db_action(request, session, current_admin.tenant_id, db_id, "start")


@router.post("/{db_id}/stop")
async def stop_database(request: Request, db_id: str, csrf_token: str = Form(...), current_admin: AdminUser = Depends(require_admin), session: AsyncSession = Depends(get_db_session)):
    verify_csrf_token(request, csrf_token)
    return await _run_db_action(request, session, current_admin.tenant_id, db_id, "stop")


@router.post("/{db_id}/restart")
async def restart_database(request: Request, db_id: str, csrf_token: str = Form(...), current_admin: AdminUser = Depends(require_admin), session: AsyncSession = Depends(get_db_session)):
    verify_csrf_token(request, csrf_token)
    return await _run_db_action(request, session, current_admin.tenant_id, db_id, "restart")
