from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db_session
from app.models import AdminUser
from app.modules.sites.service import SitesService
from app.routes import require_admin
from app.routes.deps import verify_csrf_token
from app.services.http import ProviderAPIError
from app.templating import build_templates

templates = build_templates()
router = APIRouter(prefix="/sites", tags=["sites"])


async def _run_site_action(
    request: Request,
    session: AsyncSession,
    tenant_id: str | None,
    application_id: str,
    action: str,
) -> RedirectResponse:
    if not request.state.settings.enable_provider_actions:
        return RedirectResponse(f"/sites?{action}=disabled", status_code=status.HTTP_303_SEE_OTHER)

    service = SitesService(request)
    try:
        if action == "deploy":
            result = await service.deploy_for_tenant(session, tenant_id, application_id)
            message = result.get("message", "Deployment queued.")
        elif action == "start":
            result = await service.start_for_tenant(session, tenant_id, application_id)
            message = result.get("message", "Application start requested.")
        elif action == "stop":
            result = await service.stop_for_tenant(session, tenant_id, application_id)
            message = result.get("message", "Application stop requested.")
        else:
            result = await service.restart_for_tenant(session, tenant_id, application_id)
            message = result.get("message", "Application restart requested.")
        return RedirectResponse(f"/sites?{action}={message}", status_code=status.HTTP_303_SEE_OTHER)
    except ProviderAPIError as exc:
        return RedirectResponse(f"/sites?{action}_error={str(exc)}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("")
async def list_sites(
    request: Request,
    current_admin: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    refresh = request.query_params.get("refresh") == "1"
    selected_app = request.query_params.get("app", "")
    service = SitesService(request)
    sites = []
    deployments = []
    error = None
    try:
        sites = await service.list_sites_for_tenant(session, current_admin.tenant_id, refresh=refresh)
        if selected_app:
            deployments = await service.list_deployments_for_tenant(session, current_admin.tenant_id, selected_app)
    except ProviderAPIError as exc:
        error = str(exc)
    return templates.TemplateResponse(
        request,
        "sites/index.html",
        {
            "sites": sites,
            "deployments": deployments,
            "selected_app": selected_app,
            "error": error,
            "actions_enabled": request.state.settings.enable_provider_actions and service.client.is_configured(),
            "provider_configured": service.client.is_configured(),
        },
    )


@router.post("/{application_id}/deploy")
async def deploy_site(
    request: Request,
    application_id: str,
    csrf_token: str = Form(...),
    current_admin: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    verify_csrf_token(request, csrf_token)
    return await _run_site_action(request, session, current_admin.tenant_id, application_id, "deploy")


@router.post("/{application_id}/start")
async def start_site(
    request: Request,
    application_id: str,
    csrf_token: str = Form(...),
    current_admin: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    verify_csrf_token(request, csrf_token)
    return await _run_site_action(request, session, current_admin.tenant_id, application_id, "start")


@router.post("/{application_id}/restart")
async def restart_site(
    request: Request,
    application_id: str,
    csrf_token: str = Form(...),
    current_admin: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    verify_csrf_token(request, csrf_token)
    return await _run_site_action(request, session, current_admin.tenant_id, application_id, "restart")


@router.post("/{application_id}/stop")
async def stop_site(
    request: Request,
    application_id: str,
    csrf_token: str = Form(...),
    current_admin: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    verify_csrf_token(request, csrf_token)
    return await _run_site_action(request, session, current_admin.tenant_id, application_id, "stop")


@router.get("/{application_id}")
async def site_detail(
    request: Request,
    application_id: str,
    current_admin: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    service = SitesService(request)
    site = None
    deployments = []
    envs = []
    logs = ""
    error = None
    tab = request.query_params.get("tab", "overview")
    try:
        site = await service.get_site_for_tenant(session, current_admin.tenant_id, application_id)
        deployments = await service.list_deployments_for_tenant(session, current_admin.tenant_id, application_id)
        if tab == "envs":
            envs = await service.get_envs_for_tenant(session, current_admin.tenant_id, application_id)
        if tab == "logs":
            logs = await service.get_logs_for_tenant(session, current_admin.tenant_id, application_id)
    except ProviderAPIError as exc:
        error = str(exc)
    return templates.TemplateResponse(
        request,
        "sites/detail.html",
        {
            "site": site,
            "deployments": deployments,
            "envs": envs,
            "logs": logs,
            "error": error,
            "tab": tab,
            "application_id": application_id,
            "actions_enabled": request.state.settings.enable_provider_actions and service.client.is_configured(),
        },
    )


@router.get("/{application_id}/logs")
async def site_logs_partial(
    request: Request,
    application_id: str,
    current_admin: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    service = SitesService(request)
    try:
        logs = await service.get_logs_for_tenant(session, current_admin.tenant_id, application_id)
    except ProviderAPIError:
        logs = "Failed to fetch logs."
    return templates.TemplateResponse(
        request,
        "sites/_logs_partial.html",
        {"logs": logs},
    )


@router.post("/{application_id}/deployments/{deployment_id}/cancel")
async def cancel_deployment(
    request: Request,
    application_id: str,
    deployment_id: str,
    csrf_token: str = Form(...),
    current_admin: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    verify_csrf_token(request, csrf_token)
    service = SitesService(request)
    try:
        await service.cancel_deployment_for_tenant(session, current_admin.tenant_id, application_id, deployment_id)
        return RedirectResponse(f"/sites/{application_id}?cancel=Deployment+cancelled", status_code=status.HTTP_303_SEE_OTHER)
    except ProviderAPIError as exc:
        return RedirectResponse(f"/sites/{application_id}?cancel_error={str(exc)}", status_code=status.HTTP_303_SEE_OTHER)