from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db_session
from app.models import AdminUser
from app.modules.dns.service import DnsService
from app.routes import require_admin
from app.routes.deps import verify_csrf_token
from app.services.http import ProviderAPIError
from app.templating import build_templates

templates = build_templates()
router = APIRouter(prefix="/dns", tags=["dns"])


def _redirect(zone_id: str, **params: str) -> RedirectResponse:
    qs = f"zone={zone_id}"
    for k, v in params.items():
        qs += f"&{k}={v}"
    return RedirectResponse(f"/dns?{qs}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("")
async def dns_index(
    request: Request,
    current_admin: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    refresh = request.query_params.get("refresh") == "1"
    zone_id = request.query_params.get("zone")
    service = DnsService(request)
    zones = []
    records = []
    error = request.query_params.get("error")
    success = request.query_params.get("success")
    selected_zone = ""
    try:
        zones, records, selected_zone = await service.load_for_tenant(
            session,
            current_admin.tenant_id,
            zone_id=zone_id,
            refresh=refresh,
        )
    except ProviderAPIError as exc:
        error = str(exc)
    selected_zone = selected_zone or (zones[0].id if zones else "")
    actions_enabled = request.state.settings.enable_provider_actions and service.client.is_configured()
    return templates.TemplateResponse(
        request,
        "dns/index.html",
        {
            "zones": zones,
            "records": records[:20],
            "selected_zone": selected_zone,
            "error": error,
            "success": success,
            "provider_configured": service.client.is_configured(),
            "actions_enabled": actions_enabled,
        },
    )


@router.post("/records/create")
async def create_dns_record(
    request: Request,
    zone_id: str = Form(...),
    record_type: str = Form(...),
    name: str = Form(...),
    content: str = Form(...),
    ttl: int = Form(1),
    proxied: bool = Form(False),
    csrf_token: str = Form(...),
    current_admin: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    verify_csrf_token(request, csrf_token)
    if not request.state.settings.enable_provider_actions:
        return _redirect(zone_id, error="Provider actions are disabled")
    service = DnsService(request)
    try:
        await service.create_record_for_tenant(
            session,
            current_admin.tenant_id,
            zone_id,
            record_type=record_type,
            name=name,
            content=content,
            ttl=ttl,
            proxied=proxied,
        )
        return _redirect(zone_id, success="Record created")
    except ProviderAPIError as exc:
        return _redirect(zone_id, error=str(exc))


@router.post("/records/{record_id}/edit")
async def edit_dns_record(
    request: Request,
    record_id: str,
    zone_id: str = Form(...),
    record_type: str = Form(...),
    name: str = Form(...),
    content: str = Form(...),
    ttl: int = Form(1),
    proxied: bool = Form(False),
    csrf_token: str = Form(...),
    current_admin: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    verify_csrf_token(request, csrf_token)
    if not request.state.settings.enable_provider_actions:
        return _redirect(zone_id, error="Provider actions are disabled")
    service = DnsService(request)
    try:
        await service.update_record_for_tenant(
            session,
            current_admin.tenant_id,
            zone_id,
            record_id,
            record_type=record_type,
            name=name,
            content=content,
            ttl=ttl,
            proxied=proxied,
        )
        return _redirect(zone_id, success="Record updated")
    except ProviderAPIError as exc:
        return _redirect(zone_id, error=str(exc))


@router.post("/records/{record_id}/delete")
async def delete_dns_record(
    request: Request,
    record_id: str,
    zone_id: str = Form(...),
    csrf_token: str = Form(...),
    current_admin: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    verify_csrf_token(request, csrf_token)
    if not request.state.settings.enable_provider_actions:
        return _redirect(zone_id, error="Provider actions are disabled")
    service = DnsService(request)
    try:
        await service.delete_record_for_tenant(session, current_admin.tenant_id, zone_id, record_id)
        return _redirect(zone_id, success="Record deleted")
    except ProviderAPIError as exc:
        return _redirect(zone_id, error=str(exc))
