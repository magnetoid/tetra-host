from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db_session
from app.models import AdminUser
from app.modules.dns.service import DnsService
from app.routes import require_admin
from app.services.http import ProviderAPIError
from app.templating import build_templates

templates = build_templates()
router = APIRouter(prefix="/dns", tags=["dns"])


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
    error = None
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
    return templates.TemplateResponse(
        request,
        "dns/index.html",
        {
            "zones": zones,
            "records": records[:20],
            "selected_zone": selected_zone,
            "error": error,
            "provider_configured": service.client.is_configured(),
        },
    )