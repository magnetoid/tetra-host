from typing import Any

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse

from app.models import AdminUser
from app.routes.deps import require_admin, verify_csrf_token
from app.services.coolify import CoolifyClient
from app.services.http import ProviderAPIError
from app.templating import build_templates

templates = build_templates()
router = APIRouter(prefix="/servers", tags=["servers"])


def _get_client(request: Request) -> CoolifyClient:
    return CoolifyClient.from_settings(
        http_client=request.app.state.http_client,
        cache=request.app.state.cache,
    )


@router.get("")
async def list_servers(
    request: Request,
    current_admin: AdminUser = Depends(require_admin),
):
    client = _get_client(request)
    servers = []
    error = None
    try:
        servers = await client.list_servers()
    except ProviderAPIError as exc:
        error = str(exc)
    return templates.TemplateResponse(
        request,
        "servers/index.html",
        {
            "servers": servers,
            "error": error,
        },
    )


@router.get("/{server_id}")
async def server_detail(
    request: Request,
    server_id: str,
    current_admin: AdminUser = Depends(require_admin),
):
    client = _get_client(request)
    server = None
    resources: list[dict[str, Any]] = []
    domains: list[dict[str, Any]] = []
    error = None
    try:
        servers = await client.list_servers()
        server = next((s for s in servers if s.id == server_id), None)
        resources = await client.get_server_resources(server_id)
        domains = await client.get_server_domains(server_id)
    except ProviderAPIError as exc:
        error = str(exc)
    return templates.TemplateResponse(
        request,
        "servers/detail.html",
        {
            "server": server,
            "resources": resources,
            "domains": domains,
            "error": error,
            "server_id": server_id,
        },
    )


@router.post("/{server_id}/validate")
async def validate_server(
    request: Request,
    server_id: str,
    csrf_token: str = Form(...),
    current_admin: AdminUser = Depends(require_admin),
):
    verify_csrf_token(request, csrf_token)
    client = _get_client(request)
    try:
        result = await client.validate_server(server_id)
        message = result.get("message", "Server validation requested.")
        return RedirectResponse(f"/servers/{server_id}?validate={message}", status_code=status.HTTP_303_SEE_OTHER)
    except ProviderAPIError as exc:
        return RedirectResponse(f"/servers/{server_id}?validate_error={str(exc)}", status_code=status.HTTP_303_SEE_OTHER)
