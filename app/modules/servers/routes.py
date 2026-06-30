from typing import Any

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db_session
from app.models import AdminUser
from app.models.tenant_resource import PROVIDER_COOLIFY, RESOURCE_TYPE_SERVER
from app.modules.servers.service import ServersService
from app.routes.deps import require_admin, verify_csrf_token
from app.services.coolify import CoolifyClient
from app.services.http import ProviderAPIError
from app.services.tenant_resources import TenantResourceFilter
from app.templating import build_templates

templates = build_templates()
router = APIRouter(prefix="/servers", tags=["servers"])


def _get_client(request: Request) -> CoolifyClient:
    return CoolifyClient.from_settings(
        http_client=request.app.state.http_client,
        cache=request.app.state.cache,
    )


async def _ensure_server_access(session: AsyncSession, tenant_id: str | None, server_id: str) -> None:
    allowed = await TenantResourceFilter(session, tenant_id).is_resource_accessible(
        provider=PROVIDER_COOLIFY, resource_type=RESOURCE_TYPE_SERVER, external_id=server_id
    )
    if not allowed:
        raise ProviderAPIError(service="Coolify", message="Server is not assigned to this tenant.", status_code=403)


@router.get("")
async def list_servers(request: Request, current_admin: AdminUser = Depends(require_admin), session: AsyncSession = Depends(get_db_session)):
    service = ServersService(request)
    servers = []
    error = None
    query = request.query_params.get("q", "").strip().lower()
    try:
        servers = await service.list_servers_for_tenant(session, current_admin.tenant_id)
        if query:
            servers = [s for s in servers if query in s.name.lower() or query in s.ip.lower() or query in s.description.lower()]
    except ProviderAPIError as exc:
        error = str(exc)
    return templates.TemplateResponse(request, "servers/index.html", {"servers": servers, "error": error, "q": request.query_params.get("q", "")})


@router.get("/{server_id}")
async def server_detail(request: Request, server_id: str, current_admin: AdminUser = Depends(require_admin), session: AsyncSession = Depends(get_db_session)):
    client = _get_client(request)
    server = None
    resources: list[dict[str, Any]] = []
    domains: list[dict[str, Any]] = []
    error = None
    try:
        await _ensure_server_access(session, current_admin.tenant_id, server_id)
        servers = await client.list_servers()
        filtered = await TenantResourceFilter(session, current_admin.tenant_id).filter_servers(servers)
        server = next((s for s in filtered if s.id == server_id), None)
        resources = await client.get_server_resources(server_id)
        domains = await client.get_server_domains(server_id)
    except ProviderAPIError as exc:
        error = str(exc)
    return templates.TemplateResponse(request, "servers/detail.html", {"server": server, "resources": resources, "domains": domains, "error": error, "server_id": server_id, "csrf_token": request.state.csrf_token})


@router.post("/{server_id}/validate")
async def validate_server(request: Request, server_id: str, csrf_token: str = Form(...), current_admin: AdminUser = Depends(require_admin), session: AsyncSession = Depends(get_db_session)):
    verify_csrf_token(request, csrf_token)
    client = _get_client(request)
    try:
        await _ensure_server_access(session, current_admin.tenant_id, server_id)
        result = await client.validate_server(server_id)
        message = result.get("message", "Server validation requested.")
        return RedirectResponse(f"/servers/{server_id}?validate={message}", status_code=status.HTTP_303_SEE_OTHER)
    except ProviderAPIError as exc:
        return RedirectResponse(f"/servers/{server_id}?validate_error={str(exc)}", status_code=status.HTTP_303_SEE_OTHER)
