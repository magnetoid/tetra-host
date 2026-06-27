from fastapi import APIRouter, Form, Request

from app.dependencies import require_login
from app.services.coolify import CoolifyClient
from app.services.tenants import sync_projects_for_tenant
from app.templating import build_templates

templates = build_templates()
router = APIRouter(prefix="/sites", tags=["sites"])


@router.get("")
async def list_sites(request: Request):
    redirect = await require_login(request)
    if redirect:
        return redirect
    client = CoolifyClient.from_settings()
    sites = await client.list_applications()
    sync_projects_for_tenant("cloud-industry", sites)
    return templates.TemplateResponse(
        request,
        "sites/index.html",
        {
            "sites": sites,
            "coolify_configured": client.is_configured(),
            "action_result": None,
        },
    )


@router.post("/{application_id}/actions")
async def site_action(request: Request, application_id: str, action: str = Form(...)):
    redirect = await require_login(request)
    if redirect:
        return redirect
    client = CoolifyClient.from_settings()
    action_result = await client.trigger_action(application_id, action)
    sites = await client.list_applications()
    sync_projects_for_tenant("cloud-industry", sites)
    return templates.TemplateResponse(
        request,
        "sites/index.html",
        {
            "sites": sites,
            "coolify_configured": client.is_configured(),
            "action_result": action_result,
        },
    )
