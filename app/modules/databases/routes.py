from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse

from app.models import AdminUser
from app.routes.deps import require_admin, verify_csrf_token
from app.services.coolify import CoolifyClient
from app.services.http import ProviderAPIError
from app.templating import build_templates

templates = build_templates()
router = APIRouter(prefix="/databases", tags=["databases"])


def _get_client(request: Request) -> CoolifyClient:
    return CoolifyClient.from_settings(
        http_client=request.app.state.http_client,
        cache=request.app.state.cache,
    )


@router.get("")
async def list_databases(
    request: Request,
    current_admin: AdminUser = Depends(require_admin),
):
    client = _get_client(request)
    databases = []
    error = None
    try:
        databases = await client.list_databases()
    except ProviderAPIError as exc:
        error = str(exc)
    return templates.TemplateResponse(
        request,
        "databases/index.html",
        {
            "databases": databases,
            "error": error,
            "actions_enabled": request.state.settings.enable_provider_actions and client.is_configured(),
        },
    )


async def _run_db_action(
    request: Request,
    db_id: str,
    action: str,
) -> RedirectResponse:
    if not request.state.settings.enable_provider_actions:
        return RedirectResponse(f"/databases?{action}=disabled", status_code=status.HTTP_303_SEE_OTHER)
    client = _get_client(request)
    try:
        method = getattr(client, f"{action}_database")
        result = await method(db_id)
        message = result.get("message", f"Database {action} requested.")
        return RedirectResponse(f"/databases?{action}={message}", status_code=status.HTTP_303_SEE_OTHER)
    except ProviderAPIError as exc:
        return RedirectResponse(f"/databases?{action}_error={str(exc)}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{db_id}/start")
async def start_database(
    request: Request,
    db_id: str,
    csrf_token: str = Form(...),
    current_admin: AdminUser = Depends(require_admin),
):
    verify_csrf_token(request, csrf_token)
    return await _run_db_action(request, db_id, "start")


@router.post("/{db_id}/stop")
async def stop_database(
    request: Request,
    db_id: str,
    csrf_token: str = Form(...),
    current_admin: AdminUser = Depends(require_admin),
):
    verify_csrf_token(request, csrf_token)
    return await _run_db_action(request, db_id, "stop")


@router.post("/{db_id}/restart")
async def restart_database(
    request: Request,
    db_id: str,
    csrf_token: str = Form(...),
    current_admin: AdminUser = Depends(require_admin),
):
    verify_csrf_token(request, csrf_token)
    return await _run_db_action(request, db_id, "restart")
