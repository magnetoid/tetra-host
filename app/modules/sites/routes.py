import json
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db_session
from app.models import AdminUser
from app.modules.sites.service import SitesService
from app.routes import require_admin
from app.routes.deps import verify_csrf_token
from app.services.deploy_notifications import DeploymentNotifier
from app.services.http import ProviderAPIError
from app.templating import build_templates

templates = build_templates()
router = APIRouter(prefix="/sites", tags=["sites"])


def _redirect(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=status.HTTP_303_SEE_OTHER)


async def _notify(
    request: Request,
    *,
    event: str,
    application_id: str,
    application_name: str,
    channel: str = "",
    sms_to: str = "",
    status_text: str = "",
    details: dict | None = None,
) -> None:
    notifier = DeploymentNotifier(request.app.state.http_client)
    if not notifier.is_configured():
        return
    try:
        await notifier.notify(
            event=event,
            application_id=application_id,
            application_name=application_name,
            channel=channel,
            sms_to=sms_to,
            status=status_text,
            details=details or {},
        )
    except Exception:
        return


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
    raw = None
    storages = []
    tasks = []
    task_executions = []
    error = None
    tab = request.query_params.get("tab", "overview")
    task_uuid = request.query_params.get("task_uuid", "")
    try:
        site = await service.get_site_for_tenant(session, current_admin.tenant_id, application_id)
        deployments = await service.list_deployments_for_tenant(session, current_admin.tenant_id, application_id)
        if tab == "envs":
            envs = await service.get_envs_for_tenant(session, current_admin.tenant_id, application_id)
        if tab == "logs":
            logs = await service.get_logs_for_tenant(session, current_admin.tenant_id, application_id)
        if tab == "settings":
            raw = await service.get_site_raw_for_tenant(session, current_admin.tenant_id, application_id)
        if tab == "storages":
            storages = await service.list_storages_for_tenant(session, current_admin.tenant_id, application_id)
        if tab == "tasks":
            tasks = await service.list_scheduled_tasks_for_tenant(session, current_admin.tenant_id, application_id)
            if task_uuid:
                task_executions = await service.list_scheduled_task_executions_for_tenant(
                    session, current_admin.tenant_id, application_id, task_uuid,
                )
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
            "raw": raw,
            "storages": storages,
            "tasks": tasks,
            "task_executions": task_executions,
            "task_uuid": task_uuid,
            "error": error,
            "tab": tab,
            "application_id": application_id,
            "actions_enabled": request.state.settings.enable_provider_actions and service.client.is_configured(),
            "notify_configured": bool(request.state.settings.deploy_notify_webhook_url),
            "notify_default_channel": request.state.settings.deploy_notify_default_channel,
            "notify_default_sms_to": request.state.settings.deploy_notify_sms_to,
        },
    )


@router.post("/{application_id}/deploy")
async def deploy_site(
    request: Request,
    application_id: str,
    csrf_token: str = Form(...),
    force: bool = Form(False),
    tag: str = Form(""),
    notify_channel: str = Form("none"),
    sms_to: str = Form(""),
    current_admin: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    verify_csrf_token(request, csrf_token)
    if not request.state.settings.enable_provider_actions:
        return _redirect(f"/sites/{application_id}?tab=deployments&deploy_error=Actions+disabled")
    service = SitesService(request)
    try:
        site = await service.get_site_for_tenant(session, current_admin.tenant_id, application_id)
        result = await service.deploy_for_tenant(session, current_admin.tenant_id, application_id, force=force, tag=tag)
        await _notify(
            request,
            event="requested",
            application_id=application_id,
            application_name=site.name if site else application_id,
            channel=notify_channel,
            sms_to=sms_to,
            status_text="requested",
            details={"force": force, "tag": tag, "result": result},
        )
        return _redirect(f"/sites/{application_id}?tab=deployments&deploy={quote(str(result.get('message', 'Deployment queued.')))}")
    except ProviderAPIError as exc:
        await _notify(
            request,
            event="failure",
            application_id=application_id,
            application_name=application_id,
            channel=notify_channel,
            sms_to=sms_to,
            status_text="request_failed",
            details={"error": str(exc), "force": force, "tag": tag},
        )
        return _redirect(f"/sites/{application_id}?tab=deployments&deploy_error={quote(str(exc))}")


@router.post("/{application_id}/start")
async def start_site(
    request: Request,
    application_id: str,
    csrf_token: str = Form(...),
    current_admin: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    verify_csrf_token(request, csrf_token)
    service = SitesService(request)
    try:
        result = await service.start_for_tenant(session, current_admin.tenant_id, application_id)
        return _redirect(f"/sites/{application_id}?start={quote(str(result.get('message', 'Application start requested.')))}")
    except ProviderAPIError as exc:
        return _redirect(f"/sites/{application_id}?start_error={quote(str(exc))}")


@router.post("/{application_id}/restart")
async def restart_site(
    request: Request,
    application_id: str,
    csrf_token: str = Form(...),
    current_admin: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    verify_csrf_token(request, csrf_token)
    service = SitesService(request)
    try:
        result = await service.restart_for_tenant(session, current_admin.tenant_id, application_id)
        return _redirect(f"/sites/{application_id}?restart={quote(str(result.get('message', 'Application restart requested.')))}")
    except ProviderAPIError as exc:
        return _redirect(f"/sites/{application_id}?restart_error={quote(str(exc))}")


@router.post("/{application_id}/stop")
async def stop_site(
    request: Request,
    application_id: str,
    csrf_token: str = Form(...),
    current_admin: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    verify_csrf_token(request, csrf_token)
    service = SitesService(request)
    try:
        result = await service.stop_for_tenant(session, current_admin.tenant_id, application_id)
        return _redirect(f"/sites/{application_id}?stop={quote(str(result.get('message', 'Application stop requested.')))}")
    except ProviderAPIError as exc:
        return _redirect(f"/sites/{application_id}?stop_error={quote(str(exc))}")


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
    return templates.TemplateResponse(request, "sites/_logs_partial.html", {"logs": logs})


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
        return _redirect(f"/sites/{application_id}?tab=deployments&cancel=Deployment+cancelled")
    except ProviderAPIError as exc:
        return _redirect(f"/sites/{application_id}?tab=deployments&cancel_error={quote(str(exc))}")


@router.post("/{application_id}/settings")
async def update_settings(
    request: Request,
    application_id: str,
    csrf_token: str = Form(...),
    description: str = Form(""),
    fqdn: str = Form(""),
    install_command: str = Form(""),
    build_command: str = Form(""),
    start_command: str = Form(""),
    base_directory: str = Form(""),
    publish_directory: str = Form(""),
    ports_exposes: str = Form(""),
    health_check_path: str = Form(""),
    limits_memory: str = Form(""),
    limits_cpu: str = Form(""),
    redirect: str = Form(""),
    current_admin: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    verify_csrf_token(request, csrf_token)
    service = SitesService(request)
    data: dict = {}
    for key, value in {
        "description": description,
        "fqdn": fqdn,
        "install_command": install_command,
        "build_command": build_command,
        "start_command": start_command,
        "base_directory": base_directory,
        "publish_directory": publish_directory,
        "ports_exposes": ports_exposes,
        "health_check_path": health_check_path,
        "limits_memory": limits_memory,
        "limits_cpu": limits_cpu,
        "redirect": redirect,
    }.items():
        if value:
            data[key] = value
    try:
        await service.update_site_for_tenant(session, current_admin.tenant_id, application_id, data)
        return _redirect(f"/sites/{application_id}?tab=settings&msg=Settings+saved")
    except ProviderAPIError as exc:
        return _redirect(f"/sites/{application_id}?tab=settings&error={quote(str(exc))}")


@router.post("/{application_id}/execute")
async def execute_command(
    request: Request,
    application_id: str,
    csrf_token: str = Form(...),
    command: str = Form(...),
    current_admin: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    verify_csrf_token(request, csrf_token)
    service = SitesService(request)
    try:
        output = await service.execute_command_for_tenant(session, current_admin.tenant_id, application_id, command)
        return _redirect(f"/sites/{application_id}?tab=execute&msg=Command+executed&output={quote(str(output))}")
    except ProviderAPIError as exc:
        return _redirect(f"/sites/{application_id}?tab=execute&error={quote(str(exc))}")


@router.post("/{application_id}/envs/create")
async def create_env(
    request: Request,
    application_id: str,
    csrf_token: str = Form(...),
    key: str = Form(...),
    value: str = Form(...),
    is_preview: bool = Form(False),
    is_build_time: bool = Form(False),
    current_admin: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    verify_csrf_token(request, csrf_token)
    service = SitesService(request)
    try:
        await service.create_env_for_tenant(session, current_admin.tenant_id, application_id, key, value, is_preview, is_build_time)
        return _redirect(f"/sites/{application_id}?tab=envs&msg=Variable+created")
    except ProviderAPIError as exc:
        return _redirect(f"/sites/{application_id}?tab=envs&error={quote(str(exc))}")


@router.post("/{application_id}/envs/{env_uuid}/delete")
async def delete_env(
    request: Request,
    application_id: str,
    env_uuid: str,
    csrf_token: str = Form(...),
    current_admin: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    verify_csrf_token(request, csrf_token)
    service = SitesService(request)
    try:
        await service.delete_env_for_tenant(session, current_admin.tenant_id, application_id, env_uuid)
        return _redirect(f"/sites/{application_id}?tab=envs&msg=Variable+deleted")
    except ProviderAPIError as exc:
        return _redirect(f"/sites/{application_id}?tab=envs&error={quote(str(exc))}")


@router.post("/{application_id}/storages/create")
async def create_storage(
    request: Request,
    application_id: str,
    csrf_token: str = Form(...),
    payload_json: str = Form(...),
    current_admin: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    verify_csrf_token(request, csrf_token)
    service = SitesService(request)
    try:
        payload = json.loads(payload_json)
        await service.create_storage_for_tenant(session, current_admin.tenant_id, application_id, payload)
        return _redirect(f"/sites/{application_id}?tab=storages&msg=Storage+created")
    except (ProviderAPIError, json.JSONDecodeError) as exc:
        return _redirect(f"/sites/{application_id}?tab=storages&error={quote(str(exc))}")


@router.post("/{application_id}/storages/update")
async def update_storage(
    request: Request,
    application_id: str,
    csrf_token: str = Form(...),
    payload_json: str = Form(...),
    current_admin: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    verify_csrf_token(request, csrf_token)
    service = SitesService(request)
    try:
        payload = json.loads(payload_json)
        await service.update_storage_for_tenant(session, current_admin.tenant_id, application_id, payload)
        return _redirect(f"/sites/{application_id}?tab=storages&msg=Storage+updated")
    except (ProviderAPIError, json.JSONDecodeError) as exc:
        return _redirect(f"/sites/{application_id}?tab=storages&error={quote(str(exc))}")


@router.post("/{application_id}/storages/{storage_uuid}/delete")
async def delete_storage(
    request: Request,
    application_id: str,
    storage_uuid: str,
    csrf_token: str = Form(...),
    current_admin: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    verify_csrf_token(request, csrf_token)
    service = SitesService(request)
    try:
        await service.delete_storage_for_tenant(session, current_admin.tenant_id, application_id, storage_uuid)
        return _redirect(f"/sites/{application_id}?tab=storages&msg=Storage+deleted")
    except ProviderAPIError as exc:
        return _redirect(f"/sites/{application_id}?tab=storages&error={quote(str(exc))}")


@router.post("/{application_id}/tasks/create")
async def create_task(
    request: Request,
    application_id: str,
    csrf_token: str = Form(...),
    payload_json: str = Form(...),
    current_admin: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    verify_csrf_token(request, csrf_token)
    service = SitesService(request)
    try:
        payload = json.loads(payload_json)
        await service.create_scheduled_task_for_tenant(session, current_admin.tenant_id, application_id, payload)
        return _redirect(f"/sites/{application_id}?tab=tasks&msg=Scheduled+task+created")
    except (ProviderAPIError, json.JSONDecodeError) as exc:
        return _redirect(f"/sites/{application_id}?tab=tasks&error={quote(str(exc))}")


@router.post("/{application_id}/tasks/{task_uuid}/update")
async def update_task(
    request: Request,
    application_id: str,
    task_uuid: str,
    csrf_token: str = Form(...),
    payload_json: str = Form(...),
    current_admin: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    verify_csrf_token(request, csrf_token)
    service = SitesService(request)
    try:
        payload = json.loads(payload_json)
        await service.update_scheduled_task_for_tenant(session, current_admin.tenant_id, application_id, task_uuid, payload)
        return _redirect(f"/sites/{application_id}?tab=tasks&msg=Scheduled+task+updated")
    except (ProviderAPIError, json.JSONDecodeError) as exc:
        return _redirect(f"/sites/{application_id}?tab=tasks&error={quote(str(exc))}")


@router.post("/{application_id}/tasks/{task_uuid}/delete")
async def delete_task(
    request: Request,
    application_id: str,
    task_uuid: str,
    csrf_token: str = Form(...),
    current_admin: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    verify_csrf_token(request, csrf_token)
    service = SitesService(request)
    try:
        await service.delete_scheduled_task_for_tenant(session, current_admin.tenant_id, application_id, task_uuid)
        return _redirect(f"/sites/{application_id}?tab=tasks&msg=Scheduled+task+deleted")
    except ProviderAPIError as exc:
        return _redirect(f"/sites/{application_id}?tab=tasks&error={quote(str(exc))}")
