import asyncio
import json

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.contracts import (
    AdminResponse,
    AdminSummary,
    AppActionResponse,
    AppInstallRequest,
    AppTemplateSummary,
    AuthResponse,
    DeploymentStatus,
    DeployStartResponse,
    GitDeployRequest,
    InstalledAppSummary,
    DashboardMetrics,
    DashboardResponse,
    DeploymentDetail,
    DeploymentLogLine,
    DNSRecordCreateRequest,
    DNSRecordSummary,
    DNSResponse,
    DNSZoneSummary,
    DnsExportResponse,
    DnsImportRequest,
    EnvVarCreateRequest,
    CachePurgeRequest,
    DnssecUpdateRequest,
    ZoneAnalytics,
    ZoneAnalyticsPoint,
    ZoneAnalyticsTotals,
    ZoneSettings,
    ZoneSettingUpdateRequest,
    MailboxSummary,
    MailDomainSummary,
    MailResponse,
    PlanCreateRequest,
    PlanSummary,
    PlanUpdateRequest,
    ProviderSummary,
    SignupRequest,
    SiteActionResponse,
    SiteDeploymentSummary,
    SiteSummary,
    TenantAdminCreateRequest,
    TenantCreateRequest,
    TenantResourceCreateRequest,
    TenantResourceSummary,
    TenantSummary,
)
from app.api.security import create_api_token, read_api_token
from app.db import get_db_session
from app.models import AdminUser, Tenant, TenantResource
from app.models.tenant import TENANT_ACTIVE, TENANT_PENDING, TENANT_REJECTED, TENANT_SUSPENDED
from app.models.audit import AuditEvent
from app.models.plan import Plan
from app.modules.apps.service import AppsService
from app.modules.auth.service import AuthService
from app.modules.deploys.service import DeploysService
from app.modules.dns.service import DnsService
from app.modules.plans.service import PlanService
from app.services.builder import BuildError
from app.services.docker_engine import DockerEngineError
from app.modules.mail.service import MailService
from app.modules.sites.service import SitesService
from app.services.cloudflare import count_bind_records
from app.services.coolify import parse_deployment_log_lines
from app.models.admin import ROLE_PLATFORM_ADMIN
from app.routes.deps import get_auth_service
from app.services.http import ProviderAPIError

# Coolify deployment statuses that mean the build has stopped (terminal).
_TERMINAL_DEPLOYMENT_STATES = {
    "finished",
    "success",
    "succeeded",
    "failed",
    "error",
    "cancelled",
    "canceled",
    "cancelled_by_user",
    "closed",
    "skipped",
}


def _sse_event(event: str, data: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def _stream_deployment_logs(
    client,
    deployment_id: str,
    request: Request,
    *,
    poll_interval: float = 1.5,
    max_seconds: float = 900.0,
):
    """Poll a Coolify deployment and emit incremental SSE log/status events.

    Diffs the build log by parsed line count each poll (Coolify only exposes a
    growing log string, not a stream), emits new lines + status transitions,
    and terminates on a terminal status, client disconnect, or safety timeout.
    """
    sent_lines = 0
    last_status: str | None = None
    elapsed = 0.0
    while True:
        if await request.is_disconnected():
            return
        deployment = await client.get_deployment(deployment_id)
        if deployment is None:
            yield _sse_event("error", {"message": "Deployment not found."})
            return
        if deployment.status != last_status:
            last_status = deployment.status
            yield _sse_event("status", {"status": deployment.status})
        lines = parse_deployment_log_lines(deployment.deployment_log)
        if len(lines) > sent_lines:
            for line in lines[sent_lines:]:
                yield _sse_event("log", line)
            sent_lines = len(lines)
        if deployment.status.lower() in _TERMINAL_DEPLOYMENT_STATES:
            yield _sse_event("done", {"status": deployment.status})
            return
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
        if elapsed >= max_seconds:
            yield _sse_event("done", {"status": deployment.status, "timeout": True})
            return

router = APIRouter(prefix="/api/v1", tags=["api"])


def _provider_summary(name: str, configured: bool, detail: str) -> ProviderSummary:
    return ProviderSummary(
        name=name,
        status="connected" if configured else "not_configured",
        detail=detail,
    )


def _admin_summary(admin: AdminUser) -> AdminSummary:
    return AdminSummary(
        id=admin.id,
        email=admin.email,
        full_name=admin.full_name,
        is_active=admin.is_active,
        tenant_id=admin.tenant_id,
        tenant_slug=admin.tenant.slug if admin.tenant else "",
        tenant_name=admin.tenant.name if admin.tenant else "",
        role=admin.role,
    )


def _tenant_summary(tenant: Tenant, plan_key: str = "") -> TenantSummary:
    return TenantSummary(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        is_active=tenant.is_active,
        status=tenant.status,
        plan_key=plan_key,
    )


def _tenant_resource_summary(resource: TenantResource) -> TenantResourceSummary:
    return TenantResourceSummary(
        id=resource.id,
        tenant_id=resource.tenant_id,
        tenant_slug=resource.tenant.slug if resource.tenant else "",
        tenant_name=resource.tenant.name if resource.tenant else "",
        provider=resource.provider,
        resource_type=resource.resource_type,
        external_id=resource.external_id,
        display_name=resource.display_name,
    )


async def get_current_api_admin(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    authorization: str | None = Header(default=None),
) -> AdminUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

    token = authorization.removeprefix("Bearer ").strip()
    payload = read_api_token(
        request.state.settings,
        token,
        max_age_seconds=request.state.settings.session_max_age_seconds,
    )
    admin_id = payload.get("admin_user_id") if payload else None
    if not admin_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session token.")

    auth_service = AuthService(session)
    admin = await auth_service.get_admin_by_id(admin_id)
    if admin is None or not admin.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin session is no longer valid.")
    if (
        admin.role != ROLE_PLATFORM_ADMIN
        and request.method in {"POST", "PUT", "PATCH", "DELETE"}
        and not (admin.tenant is not None and admin.tenant.status == TENANT_ACTIVE)
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant is not active.")
    return admin


async def require_platform_admin(current_admin: AdminUser = Depends(get_current_api_admin)) -> AdminUser:
    if current_admin.role != ROLE_PLATFORM_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform admin only.")
    return current_admin


@router.get("/health")
async def api_health(request: Request) -> dict[str, object]:
    return {
        "ok": True,
        "app": request.state.settings.app_name,
        "env": request.state.settings.app_env,
        "version": "python-core",
        "request_id": getattr(request.state, "request_id", ""),
    }


@router.get("/ready")
async def api_ready(request: Request) -> dict[str, object]:
    return {
        "ok": True,
        "providers": {
            "coolify": bool(request.state.settings.coolify_url and request.state.settings.coolify_token),
            "mailcow": bool(request.state.settings.mailcow_url and request.state.settings.mailcow_api_key),
            "cloudflare": bool(request.state.settings.cloudflare_api_token),
        },
        "auth": {
            "session": True,
            "csrf": True,
        },
    }


@router.post("/auth/login", response_model=AuthResponse)
async def api_login(
    request: Request,
    payload: dict[str, str],
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    email = payload.get("email", "")
    password = payload.get("password", "")
    admin = await auth_service.authenticate(email, password)
    if admin is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")
    await auth_service.touch_last_login(admin)
    token = create_api_token(request.state.settings, admin)
    return AuthResponse(token=token, admin=_admin_summary(admin))


@router.post("/auth/signup", response_model=AuthResponse)
async def api_signup(
    request: Request,
    payload: SignupRequest,
    session: AsyncSession = Depends(get_db_session),
) -> AuthResponse:
    """Public self-serve signup — unauthenticated.

    Security invariants enforced here:
    1. `SignupRequest` accepts ONLY email/password/org_name — privilege fields are never in the body.
    2. Rate-limited per client IP (signup_rate_per_hour in a 1-hour window).
    3. Capped by max_pending_tenants (anti-abuse).
    4. Duplicate email → non-distinguishing 200 with empty/non-authenticating token.
    5. The new admin is created with role=owner, status=pending by the service (never from input).
    """
    settings = request.state.settings
    client_host = request.client.host if request.client else "unknown"

    # --- Rate limit: signup_rate_per_hour requests per IP per hour ---
    limiter = request.app.state.rate_limiter
    decision = await limiter.check(
        f"signup:{client_host}",
        limit=settings.signup_rate_per_hour,
        window_seconds=3600,
    )
    if not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many signup attempts. Try again in {decision.retry_after_seconds}s.",
        )

    # --- Pending-tenant cap: anti-abuse guard ---
    pending_count = await session.scalar(
        select(func.count()).select_from(Tenant).where(Tenant.status == TENANT_PENDING)
    ) or 0
    if pending_count >= settings.max_pending_tenants:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Signup is temporarily unavailable. Please try again later.",
        )

    auth_service = AuthService(session)

    try:
        admin = await auth_service.signup(
            email=payload.email,
            password=payload.password,
            org_name=payload.org_name,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    if admin is None:
        # Duplicate email — non-distinguishing 200 with empty/non-authenticating token.
        return AuthResponse(
            token="",
            admin=AdminSummary(
                id="",
                email="",
                full_name="",
                is_active=False,
                tenant_id="",
                tenant_slug="",
                tenant_name="",
                role="",
            ),
        )

    token = create_api_token(settings, admin)
    return AuthResponse(token=token, admin=_admin_summary(admin))


@router.get("/auth/me", response_model=AdminSummary)
async def api_me(current_admin: AdminUser = Depends(get_current_api_admin)) -> AdminSummary:
    return _admin_summary(current_admin)


@router.get("/dashboard", response_model=DashboardResponse)
async def api_dashboard(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> DashboardResponse:
    sites_service = SitesService(request)
    mail_service = MailService(request)
    dns_service = DnsService(request)

    sites = []
    domains = []
    mailboxes = []
    zones = []
    providers: list[ProviderSummary] = []

    try:
        sites = await sites_service.list_sites_for_tenant(session, current_admin.tenant_id)
        detail = "Credentials missing"
        if sites_service.client.is_configured():
            detail = f"{len(sites)} applications"
        providers.append(_provider_summary("Coolify", sites_service.client.is_configured(), detail))
    except ProviderAPIError as exc:
        providers.append(ProviderSummary(name="Coolify", status="degraded", detail=str(exc)))

    try:
        domains, mailboxes = await mail_service.load_for_tenant(session, current_admin.tenant_id)
        detail = "Credentials missing"
        if mail_service.client.is_configured():
            detail = f"{len(domains)} domains · {len(mailboxes)} mailboxes"
        providers.append(_provider_summary("Mailcow", mail_service.client.is_configured(), detail))
    except ProviderAPIError as exc:
        providers.append(ProviderSummary(name="Mailcow", status="degraded", detail=str(exc)))

    try:
        zones, _records, _selected_zone = await dns_service.load_for_tenant(session, current_admin.tenant_id)
        detail = "Token missing"
        if dns_service.client.is_configured():
            detail = f"{len(zones)} DNS zones"
        providers.append(_provider_summary("Cloudflare", dns_service.client.is_configured(), detail))
    except ProviderAPIError as exc:
        providers.append(ProviderSummary(name="Cloudflare", status="degraded", detail=str(exc)))

    admin_count = await session.scalar(
        select(func.count()).select_from(AdminUser).where(AdminUser.tenant_id == current_admin.tenant_id)
    ) or 0
    unhealthy_sites = sum(1 for site in sites if "unhealthy" in site.status or "exited" in site.status)
    return DashboardResponse(
        providers=providers,
        metrics=DashboardMetrics(
            sites=len(sites),
            unhealthy_sites=unhealthy_sites,
            mail_domains=len(domains),
            dns_zones=len(zones),
            admins=int(admin_count),
        ),
    )


@router.get("/sites", response_model=list[SiteSummary])
async def api_sites(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> list[SiteSummary]:
    service = SitesService(request)
    sites = await service.list_sites_for_tenant(
        session,
        current_admin.tenant_id,
        refresh=request.query_params.get("refresh") == "1",
    )
    return [SiteSummary(**site.model_dump()) for site in sites]


@router.post("/sites/{application_id}/deploy", response_model=SiteActionResponse)
async def api_deploy_site(
    application_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> SiteActionResponse:
    service = SitesService(request)
    force = request.query_params.get("force") in {"1", "true", "yes"}
    try:
        result = await service.deploy_for_tenant(
            session, current_admin.tenant_id, application_id, force=force
        )
    except ProviderAPIError as exc:
        status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return SiteActionResponse(
        ok=bool(result.get("ok", True)),
        message=str(result.get("message", "Deployment queued.")),
        deployment_id=str(result.get("deployment_id", "")),
    )


@router.post("/sites/{application_id}/start", response_model=SiteActionResponse)
async def api_start_site(
    application_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> SiteActionResponse:
    service = SitesService(request)
    try:
        result = await service.start_for_tenant(session, current_admin.tenant_id, application_id)
    except ProviderAPIError as exc:
        status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return SiteActionResponse(ok=bool(result.get("ok", True)), message=str(result.get("message", "Application start requested.")))


@router.post("/sites/{application_id}/restart", response_model=SiteActionResponse)
async def api_restart_site(
    application_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> SiteActionResponse:
    service = SitesService(request)
    try:
        result = await service.restart_for_tenant(session, current_admin.tenant_id, application_id)
    except ProviderAPIError as exc:
        status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return SiteActionResponse(ok=bool(result.get("ok", True)), message=str(result.get("message", "Application restart requested.")))


@router.get("/sites/{application_id}/deployments", response_model=list[SiteDeploymentSummary])
async def api_site_deployments(
    application_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> list[SiteDeploymentSummary]:
    service = SitesService(request)
    try:
        deployments = await service.list_deployments_for_tenant(session, current_admin.tenant_id, application_id)
    except ProviderAPIError as exc:
        status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return [SiteDeploymentSummary(**deployment.model_dump()) for deployment in deployments]


@router.post("/sites/{application_id}/stop", response_model=SiteActionResponse)
async def api_stop_site(
    application_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> SiteActionResponse:
    service = SitesService(request)
    try:
        result = await service.stop_for_tenant(session, current_admin.tenant_id, application_id)
    except ProviderAPIError as exc:
        status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return SiteActionResponse(ok=bool(result.get("ok", True)), message=str(result.get("message", "Application stop requested.")))


@router.get("/sites/{application_id}/logs")
async def api_site_logs(
    application_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> dict[str, str]:
    service = SitesService(request)
    try:
        logs = await service.get_logs_for_tenant(session, current_admin.tenant_id, application_id)
    except ProviderAPIError as exc:
        status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return {"logs": logs}


@router.get("/sites/{application_id}/envs")
async def api_site_envs(
    application_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> list[dict[str, object]]:
    service = SitesService(request)
    try:
        envs = await service.get_envs_for_tenant(session, current_admin.tenant_id, application_id)
    except ProviderAPIError as exc:
        status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return envs


@router.post("/sites/{application_id}/envs", response_model=SiteActionResponse)
async def api_create_env(
    application_id: str,
    payload: EnvVarCreateRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> SiteActionResponse:
    service = SitesService(request)
    try:
        await service.create_env_for_tenant(
            session,
            current_admin.tenant_id,
            application_id,
            payload.key,
            payload.value,
            payload.is_preview,
            payload.is_build_time,
        )
    except ProviderAPIError as exc:
        status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return SiteActionResponse(message="Environment variable saved.")


@router.delete("/sites/{application_id}/envs/{env_uuid}", response_model=SiteActionResponse)
async def api_delete_env(
    application_id: str,
    env_uuid: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> SiteActionResponse:
    service = SitesService(request)
    try:
        await service.delete_env_for_tenant(session, current_admin.tenant_id, application_id, env_uuid)
    except ProviderAPIError as exc:
        status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return SiteActionResponse(message="Environment variable deleted.")


@router.get("/sites/{application_id}/deployments/{deployment_id}", response_model=DeploymentDetail)
async def api_deployment_detail(
    application_id: str,
    deployment_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> DeploymentDetail:
    service = SitesService(request)
    try:
        deployment = await service.get_deployment_for_tenant(
            session, current_admin.tenant_id, application_id, deployment_id
        )
    except ProviderAPIError as exc:
        status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    if deployment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found.")
    return DeploymentDetail(
        id=deployment.id,
        status=deployment.status,
        created_at=deployment.created_at,
        updated_at=deployment.updated_at,
        commit=deployment.commit,
        branch=deployment.branch,
        log_lines=[DeploymentLogLine(**line) for line in parse_deployment_log_lines(deployment.deployment_log)],
    )


@router.get("/sites/{application_id}/deployments/{deployment_id}/logs/stream")
async def api_stream_deployment_logs(
    application_id: str,
    deployment_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> StreamingResponse:
    service = SitesService(request)
    # Validate tenant access once, up front: the request DB session is not
    # safely usable inside the long-lived streaming generator below.
    try:
        await service.ensure_access_for_tenant(session, current_admin.tenant_id, application_id)
    except ProviderAPIError as exc:
        status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return StreamingResponse(
        _stream_deployment_logs(service.client, deployment_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/sites/{application_id}/deployments/{deployment_id}/cancel", response_model=SiteActionResponse)
async def api_cancel_deployment(
    application_id: str,
    deployment_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> SiteActionResponse:
    service = SitesService(request)
    try:
        result = await service.cancel_deployment_for_tenant(session, current_admin.tenant_id, application_id, deployment_id)
    except ProviderAPIError as exc:
        status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return SiteActionResponse(ok=bool(result.get("ok", True)), message=str(result.get("message", "Deployment cancelled.")))


@router.get("/mail", response_model=MailResponse)
async def api_mail(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> MailResponse:
    service = MailService(request)
    providers: list[ProviderSummary] = []
    domains = []
    mailboxes = []
    try:
        domains, mailboxes = await service.load_for_tenant(
            session,
            current_admin.tenant_id,
            refresh=request.query_params.get("refresh") == "1",
        )
        detail = "Credentials missing"
        if service.client.is_configured():
            detail = f"{len(domains)} domains · {len(mailboxes)} mailboxes"
        providers.append(_provider_summary("Mailcow", service.client.is_configured(), detail))
    except ProviderAPIError as exc:
        providers.append(ProviderSummary(name="Mailcow", status="degraded", detail=str(exc)))

    return MailResponse(
        providers=providers,
        domains=[MailDomainSummary(**domain.model_dump()) for domain in domains],
        mailboxes=[MailboxSummary(**mailbox.model_dump()) for mailbox in mailboxes],
    )


@router.get("/dns", response_model=DNSResponse)
async def api_dns(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> DNSResponse:
    service = DnsService(request)
    zone_id = request.query_params.get("zone")
    providers: list[ProviderSummary] = []
    zones = []
    records = []
    selected_zone = ""
    try:
        zones, records, selected_zone = await service.load_for_tenant(
            session,
            current_admin.tenant_id,
            zone_id=zone_id,
            refresh=request.query_params.get("refresh") == "1",
        )
        detail = "Token missing"
        if service.client.is_configured():
            detail = f"{len(zones)} DNS zones"
        providers.append(_provider_summary("Cloudflare", service.client.is_configured(), detail))
    except ProviderAPIError as exc:
        providers.append(ProviderSummary(name="Cloudflare", status="degraded", detail=str(exc)))

    selected_zone = selected_zone or (zones[0].id if zones else "")
    return DNSResponse(
        providers=providers,
        selected_zone=selected_zone,
        zones=[DNSZoneSummary(**zone.model_dump()) for zone in zones],
        records=[DNSRecordSummary(**record.model_dump()) for record in records],
    )


@router.post("/dns/zones/{zone_id}/records", response_model=SiteActionResponse)
async def api_create_dns_record(
    zone_id: str,
    payload: DNSRecordCreateRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> SiteActionResponse:
    service = DnsService(request)
    try:
        await service.create_record_for_tenant(
            session,
            current_admin.tenant_id,
            zone_id,
            record_type=payload.type,
            name=payload.name,
            content=payload.content,
            ttl=payload.ttl,
            proxied=payload.proxied,
            priority=payload.priority,
        )
    except ProviderAPIError as exc:
        status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return SiteActionResponse(message="DNS record created.")


@router.put("/dns/zones/{zone_id}/records/{record_id}", response_model=SiteActionResponse)
async def api_update_dns_record(
    zone_id: str,
    record_id: str,
    payload: DNSRecordCreateRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> SiteActionResponse:
    service = DnsService(request)
    try:
        await service.update_record_for_tenant(
            session,
            current_admin.tenant_id,
            zone_id,
            record_id,
            record_type=payload.type,
            name=payload.name,
            content=payload.content,
            ttl=payload.ttl,
            proxied=payload.proxied,
            priority=payload.priority,
        )
    except ProviderAPIError as exc:
        status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return SiteActionResponse(message="DNS record updated.")


@router.delete("/dns/zones/{zone_id}/records/{record_id}", response_model=SiteActionResponse)
async def api_delete_dns_record(
    zone_id: str,
    record_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> SiteActionResponse:
    service = DnsService(request)
    try:
        await service.delete_record_for_tenant(session, current_admin.tenant_id, zone_id, record_id)
    except ProviderAPIError as exc:
        status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return SiteActionResponse(message="DNS record deleted.")


@router.get("/dns/zones/{zone_id}/settings", response_model=ZoneSettings)
async def api_zone_settings(
    zone_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> ZoneSettings:
    service = DnsService(request)
    try:
        settings = await service.get_zone_settings_for_tenant(session, current_admin.tenant_id, zone_id)
    except ProviderAPIError as exc:
        status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return ZoneSettings(
        ssl=str(settings.get("ssl", "")),
        always_use_https=str(settings.get("always_use_https", "")),
        development_mode=str(settings.get("development_mode", "")),
        security_level=str(settings.get("security_level", "")),
        dnssec=str(settings.get("dnssec", "")),
    )


@router.patch("/dns/zones/{zone_id}/settings", response_model=SiteActionResponse)
async def api_update_zone_setting(
    zone_id: str,
    payload: ZoneSettingUpdateRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> SiteActionResponse:
    service = DnsService(request)
    try:
        await service.update_zone_setting_for_tenant(
            session, current_admin.tenant_id, zone_id, payload.setting, payload.value
        )
    except ProviderAPIError as exc:
        status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return SiteActionResponse(message=f"{payload.setting} updated.")


@router.patch("/dns/zones/{zone_id}/dnssec", response_model=SiteActionResponse)
async def api_update_dnssec(
    zone_id: str,
    payload: DnssecUpdateRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> SiteActionResponse:
    service = DnsService(request)
    try:
        await service.update_dnssec_for_tenant(session, current_admin.tenant_id, zone_id, payload.status)
    except ProviderAPIError as exc:
        status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return SiteActionResponse(message="DNSSEC updated.")


@router.post("/dns/zones/{zone_id}/purge", response_model=SiteActionResponse)
async def api_purge_cache(
    zone_id: str,
    payload: CachePurgeRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> SiteActionResponse:
    service = DnsService(request)
    try:
        await service.purge_cache_for_tenant(
            session, current_admin.tenant_id, zone_id, everything=payload.everything, files=payload.files
        )
    except ProviderAPIError as exc:
        status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return SiteActionResponse(message="Cache purge requested.")


@router.get("/dns/zones/{zone_id}/analytics", response_model=ZoneAnalytics)
async def api_zone_analytics(
    zone_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> ZoneAnalytics:
    service = DnsService(request)
    try:
        days = int(request.query_params.get("days", "7"))
    except ValueError:
        days = 7
    try:
        data = await service.get_zone_analytics_for_tenant(
            session, current_admin.tenant_id, zone_id, days=days
        )
    except ProviderAPIError as exc:
        status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return ZoneAnalytics(
        zone_id=zone_id,
        since=str(data.get("since", "")),
        until=str(data.get("until", "")),
        points=[ZoneAnalyticsPoint(**point) for point in data.get("points", [])],
        totals=ZoneAnalyticsTotals(**data.get("totals", {})),
    )


@router.get("/dns/zones/{zone_id}/export", response_model=DnsExportResponse)
async def api_export_dns_records(
    zone_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> DnsExportResponse:
    service = DnsService(request)
    try:
        bind = await service.export_records_for_tenant(session, current_admin.tenant_id, zone_id)
    except ProviderAPIError as exc:
        status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return DnsExportResponse(zone_id=zone_id, bind=bind, record_count=count_bind_records(bind))


@router.post("/dns/zones/{zone_id}/import", response_model=SiteActionResponse)
async def api_import_dns_records(
    zone_id: str,
    payload: DnsImportRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> SiteActionResponse:
    service = DnsService(request)
    if not payload.bind.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No zone file provided.")
    try:
        result = await service.import_records_for_tenant(
            session, current_admin.tenant_id, zone_id, payload.bind
        )
    except ProviderAPIError as exc:
        status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    recs_added = ((result.get("result") or {}).get("recs_added")) if isinstance(result, dict) else None
    message = f"Imported {recs_added} records." if recs_added is not None else "DNS records imported."
    return SiteActionResponse(message=message)


def _engine_exc_to_http(exc: Exception) -> HTTPException:
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None) or status.HTTP_502_BAD_GATEWAY
    return HTTPException(status_code=int(code), detail=str(exc))


@router.get("/apps/catalog", response_model=list[AppTemplateSummary])
async def api_apps_catalog(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> list[AppTemplateSummary]:
    service = AppsService(request)
    try:
        templates = await service.list_catalog(
            search=request.query_params.get("search"),
            category=request.query_params.get("category"),
        )
    except (ProviderAPIError, DockerEngineError) as exc:
        raise _engine_exc_to_http(exc) from exc
    return [
        AppTemplateSummary(
            slug=t.slug, name=t.name, description=t.description,
            category=t.category, tags=t.tags, logo=t.logo, port=t.port,
        )
        for t in templates
    ]


@router.get("/apps", response_model=list[InstalledAppSummary])
async def api_apps_installed(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> list[InstalledAppSummary]:
    service = AppsService(request)
    apps = await service.list_installed_for_tenant(session, current_admin.tenant_id)
    return [InstalledAppSummary(**app.model_dump()) for app in apps]


@router.post("/apps/install", response_model=AppActionResponse)
async def api_apps_install(
    payload: AppInstallRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> AppActionResponse:
    service = AppsService(request)
    try:
        result = await service.install_for_tenant(
            session, current_admin.tenant_id, slug=payload.slug, name=payload.name, domain=payload.domain
        )
    except (ProviderAPIError, DockerEngineError) as exc:
        raise _engine_exc_to_http(exc) from exc
    return AppActionResponse(
        message="App installed.",
        project=str(result.get("project", "")),
        domain=str(result.get("domain", "")),
    )


@router.post("/apps/{project}/start", response_model=AppActionResponse)
async def api_apps_start(
    project: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> AppActionResponse:
    service = AppsService(request)
    try:
        await service.control_for_tenant(session, current_admin.tenant_id, project, "start")
    except (ProviderAPIError, DockerEngineError) as exc:
        raise _engine_exc_to_http(exc) from exc
    return AppActionResponse(message="App started.", project=project)


@router.post("/apps/{project}/stop", response_model=AppActionResponse)
async def api_apps_stop(
    project: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> AppActionResponse:
    service = AppsService(request)
    try:
        await service.control_for_tenant(session, current_admin.tenant_id, project, "stop")
    except (ProviderAPIError, DockerEngineError) as exc:
        raise _engine_exc_to_http(exc) from exc
    return AppActionResponse(message="App stopped.", project=project)


@router.delete("/apps/{project}", response_model=AppActionResponse)
async def api_apps_remove(
    project: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> AppActionResponse:
    service = AppsService(request)
    volumes = request.query_params.get("volumes") in {"1", "true", "yes"}
    try:
        await service.remove_for_tenant(session, current_admin.tenant_id, project, volumes=volumes)
    except (ProviderAPIError, DockerEngineError) as exc:
        raise _engine_exc_to_http(exc) from exc
    return AppActionResponse(message="App removed.", project=project)


@router.get("/apps/{project}/logs")
async def api_apps_logs(
    project: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> dict[str, str]:
    service = AppsService(request)
    try:
        logs = await service.logs_for_tenant(session, current_admin.tenant_id, project)
    except (ProviderAPIError, DockerEngineError) as exc:
        raise _engine_exc_to_http(exc) from exc
    return {"logs": logs}


def _deployment_status(deployment) -> DeploymentStatus:
    return DeploymentStatus(
        id=deployment.id, project=deployment.project, status=deployment.status,
        git_url=deployment.git_url, ref=deployment.ref, builder=deployment.builder,
        image=deployment.image, commit=deployment.commit, port=deployment.port,
        domain=deployment.domain, log=deployment.log, error=deployment.error,
        created_at=deployment.created_at.isoformat() if deployment.created_at else "",
    )


@router.post("/deploys/git", response_model=DeployStartResponse)
async def api_deploy_git(
    payload: GitDeployRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> DeployStartResponse:
    service = DeploysService(request)
    try:
        deployment_id = await service.start_deploy_for_tenant(
            current_admin.tenant_id,
            git_url=payload.git_url, ref=payload.ref, name=payload.name, port=payload.port,
        )
    except (ProviderAPIError, DockerEngineError, BuildError) as exc:
        raise _engine_exc_to_http(exc) from exc
    return DeployStartResponse(deployment_id=deployment_id)


@router.get("/deploys", response_model=list[DeploymentStatus])
async def api_list_deploys(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> list[DeploymentStatus]:
    service = DeploysService(request)
    deployments = await service.list_deployments_for_tenant(session, current_admin.tenant_id)
    return [_deployment_status(deployment) for deployment in deployments]


@router.get("/deploys/{deployment_id}", response_model=DeploymentStatus)
async def api_deploy_status(
    deployment_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> DeploymentStatus:
    service = DeploysService(request)
    deployment = await service.get_deployment_for_tenant(session, current_admin.tenant_id, deployment_id)
    if deployment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found.")
    return _deployment_status(deployment)


@router.get("/admin", response_model=AdminResponse)
async def api_admin(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(require_platform_admin),
) -> AdminResponse:
    admins = list(
        (
            await session.scalars(
                select(AdminUser)
                .where(AdminUser.tenant_id == current_admin.tenant_id)
                .order_by(AdminUser.created_at)
            )
        ).all()
    )
    providers = [
        _provider_summary(
            "Coolify",
            bool(request.state.settings.coolify_url and request.state.settings.coolify_token),
            request.state.settings.coolify_url or "Missing URL and token",
        ),
        _provider_summary(
            "Mailcow",
            bool(request.state.settings.mailcow_url and request.state.settings.mailcow_api_key),
            request.state.settings.mailcow_url or "Missing URL and API key",
        ),
        _provider_summary(
            "Cloudflare",
            bool(request.state.settings.cloudflare_api_token),
            "Scoped token present" if request.state.settings.cloudflare_api_token else "Missing API token",
        ),
    ]
    return AdminResponse(admins=[_admin_summary(admin) for admin in admins], providers=providers)


@router.post("/tenants", response_model=TenantSummary)
async def api_create_tenant(
    payload: TenantCreateRequest,
    session: AsyncSession = Depends(get_db_session),
    _: AdminUser = Depends(require_platform_admin),
) -> TenantSummary:
    auth_service = AuthService(session)
    normalized_slug = auth_service.normalize_slug(payload.slug)
    existing = await auth_service.get_tenant_by_slug(normalized_slug)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tenant slug already exists.")

    tenant = Tenant(name=payload.name.strip(), slug=normalized_slug, status=TENANT_ACTIVE)
    session.add(tenant)
    await session.flush()
    return _tenant_summary(tenant)


@router.get("/tenants", response_model=list[TenantSummary])
async def api_list_tenants(
    session: AsyncSession = Depends(get_db_session),
    _: AdminUser = Depends(require_platform_admin),
) -> list[TenantSummary]:
    tenants = list((await session.scalars(select(Tenant).order_by(Tenant.created_at))).all())
    # Build a plan_id → plan_key map for all tenants in one query
    plan_ids = {t.plan_id for t in tenants if t.plan_id}
    plan_key_map: dict[str, str] = {}
    if plan_ids:
        plans = list((await session.scalars(select(Plan).where(Plan.id.in_(plan_ids)))).all())
        plan_key_map = {p.id: p.key for p in plans}
    return [_tenant_summary(t, plan_key_map.get(t.plan_id, "") if t.plan_id else "") for t in tenants]


@router.post("/tenants/{tenant_slug}/activate", response_model=TenantSummary)
async def api_activate_tenant(
    tenant_slug: str,
    session: AsyncSession = Depends(get_db_session),
    _: AdminUser = Depends(require_platform_admin),
) -> TenantSummary:
    auth_service = AuthService(session)
    tenant = await auth_service.get_tenant_by_slug(tenant_slug)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")
    tenant.status = TENANT_ACTIVE
    await session.flush()
    return _tenant_summary(tenant)


@router.post("/tenants/{tenant_slug}/deactivate", response_model=TenantSummary)
async def api_deactivate_tenant(
    tenant_slug: str,
    session: AsyncSession = Depends(get_db_session),
    _: AdminUser = Depends(require_platform_admin),
) -> TenantSummary:
    auth_service = AuthService(session)
    tenant = await auth_service.get_tenant_by_slug(tenant_slug)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")
    tenant.status = TENANT_SUSPENDED
    await session.flush()
    return _tenant_summary(tenant)


async def _resolve_plan_key(session: AsyncSession, plan_id: str | None) -> str:
    if not plan_id:
        return ""
    plan = await session.get(Plan, plan_id)
    return plan.key if plan else ""


@router.post("/tenants/{tenant_slug}/approve", response_model=TenantSummary)
async def api_approve_tenant(
    tenant_slug: str,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(require_platform_admin),
) -> TenantSummary:
    auth_service = AuthService(session)
    tenant = await auth_service.get_tenant_by_slug(tenant_slug)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")
    if tenant.status != TENANT_PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot approve a tenant in status '{tenant.status}'.",
        )
    tenant.status = TENANT_ACTIVE
    session.add(AuditEvent(
        actor_email=current_admin.email,
        action="tenant.approve",
        target=tenant_slug,
        details="",
    ))
    await session.flush()
    plan_key = await _resolve_plan_key(session, tenant.plan_id)
    return _tenant_summary(tenant, plan_key)


@router.post("/tenants/{tenant_slug}/reject", response_model=TenantSummary)
async def api_reject_tenant(
    tenant_slug: str,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(require_platform_admin),
) -> TenantSummary:
    auth_service = AuthService(session)
    tenant = await auth_service.get_tenant_by_slug(tenant_slug)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")
    if tenant.status != TENANT_PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot reject a tenant in status '{tenant.status}'.",
        )
    tenant.status = TENANT_REJECTED
    session.add(AuditEvent(
        actor_email=current_admin.email,
        action="tenant.reject",
        target=tenant_slug,
        details="",
    ))
    await session.flush()
    plan_key = await _resolve_plan_key(session, tenant.plan_id)
    return _tenant_summary(tenant, plan_key)


@router.post("/tenants/{tenant_slug}/suspend", response_model=TenantSummary)
async def api_suspend_tenant(
    tenant_slug: str,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(require_platform_admin),
) -> TenantSummary:
    auth_service = AuthService(session)
    tenant = await auth_service.get_tenant_by_slug(tenant_slug)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")
    if tenant.status != TENANT_ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot suspend a tenant in status '{tenant.status}'.",
        )
    tenant.status = TENANT_SUSPENDED
    session.add(AuditEvent(
        actor_email=current_admin.email,
        action="tenant.suspend",
        target=tenant_slug,
        details="",
    ))
    await session.flush()
    plan_key = await _resolve_plan_key(session, tenant.plan_id)
    return _tenant_summary(tenant, plan_key)


@router.post("/tenants/{tenant_slug}/reactivate", response_model=TenantSummary)
async def api_reactivate_tenant(
    tenant_slug: str,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(require_platform_admin),
) -> TenantSummary:
    auth_service = AuthService(session)
    tenant = await auth_service.get_tenant_by_slug(tenant_slug)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")
    if tenant.status != TENANT_SUSPENDED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot reactivate a tenant in status '{tenant.status}'.",
        )
    tenant.status = TENANT_ACTIVE
    session.add(AuditEvent(
        actor_email=current_admin.email,
        action="tenant.reactivate",
        target=tenant_slug,
        details="",
    ))
    await session.flush()
    plan_key = await _resolve_plan_key(session, tenant.plan_id)
    return _tenant_summary(tenant, plan_key)


@router.post("/tenant-admins", response_model=AdminSummary)
async def api_create_tenant_admin(
    payload: TenantAdminCreateRequest,
    session: AsyncSession = Depends(get_db_session),
    _: AdminUser = Depends(require_platform_admin),
) -> AdminSummary:
    auth_service = AuthService(session)
    tenant = await auth_service.get_tenant_by_slug(payload.tenant_slug)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")

    normalized_email = auth_service.normalize_email(payload.email)
    existing = await auth_service.get_admin_by_email(normalized_email)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Admin email already exists.")

    admin = AdminUser(
        tenant_id=tenant.id,
        email=normalized_email,
        full_name=payload.full_name.strip(),
        password_hash=auth_service.hash_password(payload.password),
        is_active=True,
    )
    session.add(admin)
    await session.flush()
    refreshed = await auth_service.get_admin_by_id(admin.id)
    assert refreshed is not None
    return _admin_summary(refreshed)


@router.post("/tenant-resources", response_model=TenantResourceSummary)
async def api_create_tenant_resource(
    payload: TenantResourceCreateRequest,
    session: AsyncSession = Depends(get_db_session),
    _: AdminUser = Depends(require_platform_admin),
) -> TenantResourceSummary:
    auth_service = AuthService(session)
    tenant = await auth_service.get_tenant_by_slug(payload.tenant_slug)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")

    resource = await session.scalar(
        select(TenantResource).where(
            TenantResource.provider == payload.provider.strip().lower(),
            TenantResource.resource_type == payload.resource_type.strip().lower(),
            TenantResource.external_id == payload.external_id.strip(),
        )
    )
    if resource is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource already assigned.")

    resource = TenantResource(
        tenant_id=tenant.id,
        provider=payload.provider.strip().lower(),
        resource_type=payload.resource_type.strip().lower(),
        external_id=payload.external_id.strip(),
        display_name=payload.display_name.strip() or payload.external_id.strip(),
    )
    session.add(resource)
    await session.flush()
    await session.refresh(resource, attribute_names=["tenant"])
    return _tenant_resource_summary(resource)


# ---------------------------------------------------------------------------
# Plans endpoints  (/api/v1/plans)
# ---------------------------------------------------------------------------

def _plan_summary(plan) -> PlanSummary:
    return PlanSummary(
        id=plan.id,
        key=plan.key,
        name=plan.name,
        description=plan.description,
        price_cents=plan.price_cents,
        currency=plan.currency,
        max_apps=plan.max_apps,
        max_domains=plan.max_domains,
        cpu_millicores=plan.cpu_millicores,
        mem_mb=plan.mem_mb,
        disk_mb=plan.disk_mb,
        is_archived=plan.is_archived,
        sort_order=plan.sort_order,
    )


@router.get("/plans", response_model=list[PlanSummary])
async def api_list_plans(
    include_archived: bool = False,
    session: AsyncSession = Depends(get_db_session),
    _: AdminUser = Depends(get_current_api_admin),
) -> list[PlanSummary]:
    service = PlanService(session)
    plans = await service.list_plans(include_archived=include_archived)
    return [_plan_summary(p) for p in plans]


@router.post("/plans", response_model=PlanSummary)
async def api_create_plan(
    payload: PlanCreateRequest,
    session: AsyncSession = Depends(get_db_session),
    _: AdminUser = Depends(require_platform_admin),
) -> PlanSummary:
    service = PlanService(session)
    try:
        plan = await service.create(
            key=payload.key,
            name=payload.name,
            description=payload.description,
            price_cents=payload.price_cents,
            currency=payload.currency,
            max_apps=payload.max_apps,
            max_domains=payload.max_domains,
            cpu_millicores=payload.cpu_millicores,
            mem_mb=payload.mem_mb,
            disk_mb=payload.disk_mb,
            sort_order=payload.sort_order,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return _plan_summary(plan)


@router.patch("/plans/{plan_id}", response_model=PlanSummary)
async def api_update_plan(
    plan_id: str,
    payload: PlanUpdateRequest,
    session: AsyncSession = Depends(get_db_session),
    _: AdminUser = Depends(require_platform_admin),
) -> PlanSummary:
    service = PlanService(session)
    update_fields = payload.model_dump(exclude_none=True)
    try:
        plan = await service.update(plan_id, **update_fields)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found.")
    return _plan_summary(plan)


@router.post("/plans/{plan_id}/archive", response_model=PlanSummary)
async def api_archive_plan(
    plan_id: str,
    session: AsyncSession = Depends(get_db_session),
    _: AdminUser = Depends(require_platform_admin),
) -> PlanSummary:
    service = PlanService(session)
    plan = await service.archive(plan_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found.")
    return _plan_summary(plan)
