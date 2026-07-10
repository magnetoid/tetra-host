import asyncio
import json

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.contracts import (
    AppComputeResponse,
    AppComputeSample,
    AppEnvVarRequest,
    AppEnvVarSummary,
    DeployHookCreated,
    DeployHookRequest,
    DeployHookSummary,
    DomainRequest,
    DomainSummary,
    InfraServerCreateRequest,
    InfraServerCreated,
    InfraServerSummary,
    AccountUpdateRequest,
    AdminResponse,
    AdminSummary,
    AppActionResponse,
    AppInstallRequest,
    AppTemplateSummary,
    AuditEventSummary,
    AuditLogResponse,
    AuthResponse,
    AiChatRequest,
    AiChatResponse,
    AiChatUsage,
    AiKeyCreated,
    AiKeyProvisionRequest,
    AiKeySummary,
    AiKeyUpdateRequest,
    AiModelSummary,
    AiStatusResponse,
    AiUsageEventSummary,
    AiUsageReport,
    CreditBalanceResponse,
    CreditTopupRequest,
    CreditTransactionSummary,
    TenantCreditOverview,
    CloudflarePlanSummary,
    PlanActivateRequest,
    PriceQuote,
    PricingRuleRequest,
    PricingRuleSummary,
    ResellableServiceSummary,
    ResellerChargeSummary,
    ServiceActivateResponse,
    ZoneSubscriptionSummary,
    BuildDiagnosis,
    BackupConfigSummary,
    BackupCreateRequest,
    BucketCreated,
    BucketProvisionRequest,
    BucketSummary,
    CachePurgeRequest,
    JobCreateRequest,
    JobRunSummary,
    JobUpdateRequest,
    ScheduledJobSummary,
    AcceptInviteRequest,
    InviteCreateRequest,
    InviteCreateResponse,
    InvitePreviewResponse,
    RoleChangeRequest,
    TeamInviteSummary,
    TeamMemberSummary,
    TeamResponse,
    DatabaseProvisionRequest,
    DatabaseSummary,
    DatabaseTargetOption,
    DatabaseTargets,
    DashboardMetrics,
    StatusComponent,
    StatusResponse,
    StorageStatusResponse,
    DashboardResponse,
    DeploymentDetail,
    DeploymentLogLine,
    DeploymentStatus,
    DeployStartResponse,
    DNSRecordCreateRequest,
    DNSRecordSummary,
    DNSResponse,
    DNSZoneSummary,
    DnsExportResponse,
    DnsImportRequest,
    DnssecUpdateRequest,
    EnvVarCreateRequest,
    GitDeployRequest,
    InstalledAppSummary,
    MailAliasCreateRequest,
    MailAliasSummary,
    MailboxCreateRequest,
    MailboxSummary,
    MailDkimResponse,
    MailDnsRecordReport,
    MailDomainCreateRequest,
    MailDomainCreateResponse,
    MailDomainSummary,
    MailRelayhostCreateRequest,
    MailRelayhostCreateResponse,
    MailRelayhostSummary,
    MailResponse,
    PasswordChangeRequest,
    PlanCreateRequest,
    PlanSummary,
    PlanUpdateRequest,
    PlatformAiSummary,
    PlatformOverview,
    PlatformResourceUsage,
    PlatformRevenue,
    PlatformTotals,
    PreviewSummary,
    ProjectAnalytics,
    ProjectErrors,
    ProviderSummary,
    SignupRequest,
    ActionResponse,
    ProjectDeploymentSummary,
    ProjectSummary,
    TenantAdminCreateRequest,
    TenantCreateRequest,
    TenantResourceCreateRequest,
    TenantResourceSummary,
    TenantStatusCounts,
    TenantSummary,
    UsageResponse,
    ZoneAnalytics,
    ZoneAnalyticsPoint,
    ZoneAnalyticsTotals,
    ZoneSettings,
    ZoneSettingUpdateRequest,
)
from app.config import get_settings
from app.api.security import create_api_token, read_api_token
from app.db import get_db_session
from app.models import AdminUser, Tenant, TenantResource
from app.models.tenant import TENANT_ACTIVE, TENANT_PENDING, TENANT_REJECTED, TENANT_SUSPENDED
from app.models.tenant_resource import RESOURCE_TYPE_APP, RESOURCE_TYPE_DATABASE
from app.models.audit import AuditEvent
from app.models.plan import Plan
from app.modules.analytics.service import AnalyticsService
from app.modules.apps.service import AppsService
from app.modules.auth.service import AuthService
from app.modules.databases.service import DatabasesService
from app.modules.deploys.service import DeploysService
from app.modules.domains.service import DomainsService
from app.modules.dns.service import DnsService
from app.modules.errors.service import ErrorsService
from app.modules.plans.service import PlanService
from app.models.billing import (
    MICRO_USD_PER_USD,
    AiUsageEvent,
    ResellerCharge,
    TenantCredit,
)
from app.modules.billing.credits import CreditService
from app.modules.billing.service import BillingError, BillingService, compute_resale_cents
from app.modules.jobs.service import JobError, JobsService
from app.modules.team.service import TeamError, TeamService
from app.modules.reseller.ai_service import AiResellerService
from app.modules.reseller.storage_service import StorageService
from app.modules.reseller.service import ResellerError, ResellerService
from app.services.builder import BuildError
from app.services.docker_engine import DockerEngineError
from app.modules.mail.service import MailService
from app.modules.projects.service import ProjectsService
from app.services.cloudflare import CloudflareClient, count_bind_records
from app.services.coolify import parse_deployment_log_lines
from app.models.admin import ROLE_OWNER, ROLE_PLATFORM_ADMIN
from app.models.tenant_resource import RESOURCE_TYPE_DNS_ZONE
from app.routes.deps import get_auth_service
from app.services.http import ProviderAPIError
from app.services.github_webhook import branch_from_ref, push_ref, verify_signature
from app.services.hetzner import (
    DEFAULT_CLOUD_INIT,
    HetznerClient,
    mailcow_cloud_init,
    normalize_server,
)
from app.services.quota import QuotaService
from app.services.secrets import decrypt

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
        tenant_status=admin.tenant.status if admin.tenant else "",
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


def _audit_event_summary(event: AuditEvent) -> AuditEventSummary:
    return AuditEventSummary(
        actor_email=event.actor_email,
        action=event.action,
        target=event.target,
        details=event.details,
        created_at=event.created_at.isoformat() if event.created_at else "",
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


async def require_tenant_owner(current_admin: AdminUser = Depends(get_current_api_admin)) -> AdminUser:
    """Team-management writes (invite/revoke/role/remove) are owner-gated.
    Platform admins pass through for cross-tenant support."""
    if current_admin.role not in {ROLE_OWNER, ROLE_PLATFORM_ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the tenant owner can manage the team.",
        )
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


@router.get("/status", response_model=StatusResponse)
async def api_status(request: Request) -> StatusResponse:
    """PUBLIC platform status page feed. Liveness of the control plane + configured providers,
    cached 30s so public traffic can't amplify into provider load."""
    from datetime import UTC, datetime

    from app.services.cloudflare import CloudflareClient
    from app.services.coolify import CoolifyClient

    async def compute() -> dict:
        http = request.app.state.http_client
        cache = request.app.state.cache
        components: list[dict] = [
            {"name": "Control plane API", "status": "operational", "detail": "Responding"}
        ]

        coolify = CoolifyClient.from_settings(http_client=http, cache=cache)
        if coolify.is_configured():
            try:
                await coolify.list_projects()
                components.append({"name": "Applications", "status": "operational", "detail": "Reachable"})
            except ProviderAPIError as exc:
                components.append({"name": "Applications", "status": "degraded", "detail": str(exc)[:120]})

        cloudflare = CloudflareClient.from_settings(http_client=http, cache=cache)
        if cloudflare.is_configured():
            try:
                await cloudflare.list_zones()
                components.append({"name": "DNS", "status": "operational", "detail": "Reachable"})
            except ProviderAPIError as exc:
                components.append({"name": "DNS", "status": "degraded", "detail": str(exc)[:120]})

        settings = request.state.settings
        if settings.openrouter_runtime_key or settings.openrouter_provisioning_key:
            components.append({"name": "AI gateway", "status": "operational", "detail": "Configured"})

        statuses = {c["status"] for c in components}
        overall = "down" if "down" in statuses else "degraded" if "degraded" in statuses else "operational"
        return {"overall": overall, "updated_at": datetime.now(UTC).isoformat(), "components": components}

    data = await request.app.state.cache.get_or_set("status:public", 30, compute)
    return StatusResponse(
        overall=data["overall"],
        updated_at=data["updated_at"],
        components=[StatusComponent(**c) for c in data["components"]],
    )


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

    # --- Pending-tenant cap: global anti-abuse guard ---
    pending_count = await session.scalar(
        select(func.count()).select_from(Tenant).where(Tenant.status == TENANT_PENDING)
    ) or 0
    if pending_count >= settings.max_pending_tenants:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Signup is temporarily unavailable. Please try again later.",
        )

    # --- Per-IP pending-tenant cap: prevent a single source from filling the global cap ---
    pending_from_ip = await session.scalar(
        select(func.count()).select_from(Tenant).where(
            Tenant.status == TENANT_PENDING,
            Tenant.signup_ip == client_host,
        )
    ) or 0
    if pending_from_ip >= settings.max_pending_tenants_per_ip:
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
            signup_ip=client_host,
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


@router.patch("/account", response_model=AdminSummary)
async def api_account_update(
    payload: AccountUpdateRequest,
    current_admin: AdminUser = Depends(get_current_api_admin),
    session: AsyncSession = Depends(get_db_session),
) -> AdminSummary:
    """Update the signed-in admin's own name/email."""
    try:
        admin = await AuthService(session).update_profile(
            current_admin, full_name=payload.full_name, email=payload.email
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _admin_summary(admin)


@router.post("/account/password")
async def api_account_password(
    payload: PasswordChangeRequest,
    current_admin: AdminUser = Depends(get_current_api_admin),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, bool]:
    """Change the signed-in admin's own password (verifies the current one)."""
    try:
        await AuthService(session).change_password(
            current_admin,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"ok": True}


@router.get("/dashboard", response_model=DashboardResponse)
async def api_dashboard(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> DashboardResponse:
    projects_service = ProjectsService(request)
    mail_service = MailService(request)
    dns_service = DnsService(request)

    sites = []
    domains = []
    mailboxes = []
    zones = []
    providers: list[ProviderSummary] = []

    try:
        sites = await projects_service.list_sites_for_tenant(session, current_admin.tenant_id)
        detail = "Credentials missing"
        if projects_service.client.is_configured():
            detail = f"{len(sites)} applications"
        providers.append(_provider_summary("Coolify", projects_service.client.is_configured(), detail))
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
            projects=len(sites),
            unhealthy_projects=unhealthy_sites,
            mail_domains=len(domains),
            dns_zones=len(zones),
            admins=int(admin_count),
        ),
    )


@router.get("/projects", response_model=list[ProjectSummary])
async def api_projects(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> list[ProjectSummary]:
    service = ProjectsService(request)
    sites = await service.list_sites_for_tenant(
        session,
        current_admin.tenant_id,
        refresh=request.query_params.get("refresh") == "1",
    )
    return [ProjectSummary(**site.model_dump()) for site in sites]


@router.post("/projects/{application_id}/deploy", response_model=ActionResponse)
async def api_deploy_project(
    application_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> ActionResponse:
    service = ProjectsService(request)
    force = request.query_params.get("force") in {"1", "true", "yes"}
    try:
        result = await service.deploy_for_tenant(
            session, current_admin.tenant_id, application_id, force=force
        )
    except ProviderAPIError as exc:
        status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return ActionResponse(
        ok=bool(result.get("ok", True)),
        message=str(result.get("message", "Deployment queued.")),
        deployment_id=str(result.get("deployment_id", "")),
    )


@router.post("/projects/{application_id}/start", response_model=ActionResponse)
async def api_start_project(
    application_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> ActionResponse:
    service = ProjectsService(request)
    try:
        result = await service.start_for_tenant(session, current_admin.tenant_id, application_id)
    except ProviderAPIError as exc:
        status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return ActionResponse(ok=bool(result.get("ok", True)), message=str(result.get("message", "Application start requested.")))


@router.post("/projects/{application_id}/restart", response_model=ActionResponse)
async def api_restart_project(
    application_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> ActionResponse:
    service = ProjectsService(request)
    try:
        result = await service.restart_for_tenant(session, current_admin.tenant_id, application_id)
    except ProviderAPIError as exc:
        status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return ActionResponse(ok=bool(result.get("ok", True)), message=str(result.get("message", "Application restart requested.")))


@router.get("/projects/{application_id}/deployments", response_model=list[ProjectDeploymentSummary])
async def api_project_deployments(
    application_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> list[ProjectDeploymentSummary]:
    service = ProjectsService(request)
    try:
        deployments = await service.list_deployments_for_tenant(session, current_admin.tenant_id, application_id)
    except ProviderAPIError as exc:
        status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return [ProjectDeploymentSummary(**deployment.model_dump()) for deployment in deployments]


@router.post("/projects/{application_id}/stop", response_model=ActionResponse)
async def api_stop_project(
    application_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> ActionResponse:
    service = ProjectsService(request)
    try:
        result = await service.stop_for_tenant(session, current_admin.tenant_id, application_id)
    except ProviderAPIError as exc:
        status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return ActionResponse(ok=bool(result.get("ok", True)), message=str(result.get("message", "Application stop requested.")))


@router.get("/projects/{application_id}/logs")
async def api_project_logs(
    application_id: str,
    request: Request,
    lines: int = 200,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> dict[str, str]:
    service = ProjectsService(request)
    try:
        logs = await service.get_logs_for_tenant(
            session, current_admin.tenant_id, application_id, lines=max(1, min(lines, 1000))
        )
    except ProviderAPIError as exc:
        status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return {"logs": logs}


@router.get("/projects/{application_id}/analytics", response_model=ProjectAnalytics)
async def api_project_analytics(
    application_id: str,
    request: Request,
    period: str = "7d",
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> ProjectAnalytics:
    service = AnalyticsService(request)
    try:
        data = await service.get_analytics_for_project(
            session, current_admin.tenant_id, application_id, period=period
        )
    except ProviderAPIError as exc:
        status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return ProjectAnalytics(**data)


@router.get("/projects/{application_id}/errors", response_model=ProjectErrors)
async def api_project_errors(
    application_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> ProjectErrors:
    service = ErrorsService(request)
    try:
        data = await service.get_errors_for_project(
            session, current_admin.tenant_id, application_id
        )
    except ProviderAPIError as exc:
        status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return ProjectErrors(**data)


@router.get("/projects/{application_id}/envs")
async def api_project_envs(
    application_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> list[dict[str, object]]:
    service = ProjectsService(request)
    try:
        envs = await service.get_envs_for_tenant(session, current_admin.tenant_id, application_id)
    except ProviderAPIError as exc:
        status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return envs


@router.post("/projects/{application_id}/envs", response_model=ActionResponse)
async def api_create_env(
    application_id: str,
    payload: EnvVarCreateRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> ActionResponse:
    service = ProjectsService(request)
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
    return ActionResponse(message="Environment variable saved.")


@router.delete("/projects/{application_id}/envs/{env_uuid}", response_model=ActionResponse)
async def api_delete_env(
    application_id: str,
    env_uuid: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> ActionResponse:
    service = ProjectsService(request)
    try:
        await service.delete_env_for_tenant(session, current_admin.tenant_id, application_id, env_uuid)
    except ProviderAPIError as exc:
        status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return ActionResponse(message="Environment variable deleted.")


@router.get("/projects/{application_id}/deployments/{deployment_id}", response_model=DeploymentDetail)
async def api_deployment_detail(
    application_id: str,
    deployment_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> DeploymentDetail:
    service = ProjectsService(request)
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


@router.get("/projects/{application_id}/deployments/{deployment_id}/logs/stream")
async def api_stream_deployment_logs(
    application_id: str,
    deployment_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> StreamingResponse:
    service = ProjectsService(request)
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


@router.post("/projects/{application_id}/deployments/{deployment_id}/cancel", response_model=ActionResponse)
async def api_cancel_deployment(
    application_id: str,
    deployment_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> ActionResponse:
    service = ProjectsService(request)
    try:
        result = await service.cancel_deployment_for_tenant(session, current_admin.tenant_id, application_id, deployment_id)
    except ProviderAPIError as exc:
        status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return ActionResponse(ok=bool(result.get("ok", True)), message=str(result.get("message", "Deployment cancelled.")))


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


@router.post("/mail/domains", response_model=MailDomainCreateResponse)
async def api_create_mail_domain(
    payload: MailDomainCreateRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> MailDomainCreateResponse:
    service = MailService(request)
    try:
        result = await service.create_domain_for_tenant(
            session, current_admin.tenant_id, payload.domain,
            description=payload.description, quota_mb=payload.quota_mb,
        )
    except ProviderAPIError as exc:
        raise HTTPException(
            status_code=exc.status_code or status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc
    return MailDomainCreateResponse(
        domain=result["domain"],
        dkim_name=result["dkim_name"],
        dkim_txt=result["dkim_txt"],
        relay_assigned=result["relay_assigned"],
        dns_zone=result["dns_zone"],
        dns_records=[MailDnsRecordReport(**record) for record in result["dns_records"]],
    )


@router.delete("/mail/domains/{domain}", response_model=ActionResponse)
async def api_delete_mail_domain(
    domain: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> ActionResponse:
    service = MailService(request)
    try:
        await service.delete_domain_for_tenant(session, current_admin.tenant_id, domain)
    except ProviderAPIError as exc:
        raise HTTPException(
            status_code=exc.status_code or status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc
    return ActionResponse(
        message=f"Mail domain {domain} deleted. DNS records were left in place — "
        "remove MX/SPF/DKIM/DMARC manually if the domain is retired."
    )


@router.post("/mail/mailboxes", response_model=ActionResponse)
async def api_create_mailbox(
    payload: MailboxCreateRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> ActionResponse:
    service = MailService(request)
    try:
        username = await service.create_mailbox_for_tenant(
            session, current_admin.tenant_id,
            local_part=payload.local_part, domain=payload.domain,
            password=payload.password, name=payload.name, quota_mb=payload.quota_mb,
        )
    except ProviderAPIError as exc:
        raise HTTPException(
            status_code=exc.status_code or status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc
    return ActionResponse(message=f"Mailbox {username} created.")


@router.delete("/mail/mailboxes/{username}", response_model=ActionResponse)
async def api_delete_mailbox(
    username: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> ActionResponse:
    service = MailService(request)
    try:
        await service.delete_mailbox_for_tenant(session, current_admin.tenant_id, username)
    except ProviderAPIError as exc:
        raise HTTPException(
            status_code=exc.status_code or status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc
    return ActionResponse(message=f"Mailbox {username} deleted.")


@router.get("/mail/aliases", response_model=list[MailAliasSummary])
async def api_mail_aliases(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> list[MailAliasSummary]:
    service = MailService(request)
    try:
        aliases = await service.aliases_for_tenant(
            session, current_admin.tenant_id,
            refresh=request.query_params.get("refresh") == "1",
        )
    except ProviderAPIError as exc:
        raise HTTPException(
            status_code=exc.status_code or status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc
    return [MailAliasSummary(**alias.model_dump()) for alias in aliases]


@router.post("/mail/aliases", response_model=ActionResponse)
async def api_create_mail_alias(
    payload: MailAliasCreateRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> ActionResponse:
    service = MailService(request)
    try:
        await service.create_alias_for_tenant(
            session, current_admin.tenant_id, address=payload.address, goto=payload.goto
        )
    except ProviderAPIError as exc:
        raise HTTPException(
            status_code=exc.status_code or status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc
    return ActionResponse(message=f"Alias {payload.address} → {payload.goto} created.")


@router.delete("/mail/aliases/{alias_id}", response_model=ActionResponse)
async def api_delete_mail_alias(
    alias_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> ActionResponse:
    service = MailService(request)
    try:
        await service.delete_alias_for_tenant(session, current_admin.tenant_id, alias_id)
    except ProviderAPIError as exc:
        raise HTTPException(
            status_code=exc.status_code or status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc
    return ActionResponse(message=f"Alias {alias_id} deleted.")


@router.get("/mail/domains/{domain}/dkim", response_model=MailDkimResponse)
async def api_mail_dkim(
    domain: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> MailDkimResponse:
    service = MailService(request)
    try:
        dkim = await service.dkim_for_tenant(session, current_admin.tenant_id, domain)
    except ProviderAPIError as exc:
        raise HTTPException(
            status_code=exc.status_code or status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc
    return MailDkimResponse(**dkim)


@router.get("/mail/relayhosts", response_model=list[MailRelayhostSummary])
async def api_list_mail_relayhosts(
    request: Request,
    _: AdminUser = Depends(require_platform_admin),
) -> list[MailRelayhostSummary]:
    service = MailService(request)
    try:
        hosts = await service.list_relayhosts()
    except ProviderAPIError as exc:
        raise HTTPException(
            status_code=exc.status_code or status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc
    return [MailRelayhostSummary(**host) for host in hosts]


@router.post("/mail/relayhosts", response_model=MailRelayhostCreateResponse)
async def api_create_mail_relayhost(
    payload: MailRelayhostCreateRequest,
    request: Request,
    _: AdminUser = Depends(require_platform_admin),
) -> MailRelayhostCreateResponse:
    """ESP relay credentials are a platform secret — platform admins only."""
    service = MailService(request)
    try:
        relayhost_id = await service.create_relayhost(
            hostname=payload.hostname, username=payload.username, password=payload.password
        )
    except ProviderAPIError as exc:
        raise HTTPException(
            status_code=exc.status_code or status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc
    return MailRelayhostCreateResponse(relayhost_id=relayhost_id)


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


@router.post("/dns/zones/{zone_id}/records", response_model=ActionResponse)
async def api_create_dns_record(
    zone_id: str,
    payload: DNSRecordCreateRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> ActionResponse:
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
    return ActionResponse(message="DNS record created.")


@router.put("/dns/zones/{zone_id}/records/{record_id}", response_model=ActionResponse)
async def api_update_dns_record(
    zone_id: str,
    record_id: str,
    payload: DNSRecordCreateRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> ActionResponse:
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
    return ActionResponse(message="DNS record updated.")


@router.delete("/dns/zones/{zone_id}/records/{record_id}", response_model=ActionResponse)
async def api_delete_dns_record(
    zone_id: str,
    record_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> ActionResponse:
    service = DnsService(request)
    try:
        await service.delete_record_for_tenant(session, current_admin.tenant_id, zone_id, record_id)
    except ProviderAPIError as exc:
        status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return ActionResponse(message="DNS record deleted.")


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


@router.patch("/dns/zones/{zone_id}/settings", response_model=ActionResponse)
async def api_update_zone_setting(
    zone_id: str,
    payload: ZoneSettingUpdateRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> ActionResponse:
    service = DnsService(request)
    try:
        await service.update_zone_setting_for_tenant(
            session, current_admin.tenant_id, zone_id, payload.setting, payload.value
        )
    except ProviderAPIError as exc:
        status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return ActionResponse(message=f"{payload.setting} updated.")


@router.patch("/dns/zones/{zone_id}/dnssec", response_model=ActionResponse)
async def api_update_dnssec(
    zone_id: str,
    payload: DnssecUpdateRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> ActionResponse:
    service = DnsService(request)
    try:
        await service.update_dnssec_for_tenant(session, current_admin.tenant_id, zone_id, payload.status)
    except ProviderAPIError as exc:
        status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return ActionResponse(message="DNSSEC updated.")


@router.post("/dns/zones/{zone_id}/purge", response_model=ActionResponse)
async def api_purge_cache(
    zone_id: str,
    payload: CachePurgeRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> ActionResponse:
    service = DnsService(request)
    try:
        await service.purge_cache_for_tenant(
            session, current_admin.tenant_id, zone_id, everything=payload.everything, files=payload.files
        )
    except ProviderAPIError as exc:
        status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return ActionResponse(message="Cache purge requested.")


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


@router.post("/dns/zones/{zone_id}/import", response_model=ActionResponse)
async def api_import_dns_records(
    zone_id: str,
    payload: DnsImportRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> ActionResponse:
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
    return ActionResponse(message=message)


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


@router.get("/apps/{project}/compute", response_model=AppComputeResponse)
async def api_apps_compute(
    project: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> AppComputeResponse:
    """Live per-container CPU/mem/net snapshot for a tenant's app (Vercel-style compute)."""
    service = AppsService(request)
    try:
        samples = await service.compute_for_tenant(session, current_admin.tenant_id, project)
    except (ProviderAPIError, DockerEngineError) as exc:
        raise _engine_exc_to_http(exc) from exc
    out = [
        AppComputeSample(
            name=s.name, cpu_percent=s.cpu_percent, mem_used_mb=s.mem_used_mb,
            mem_limit_mb=s.mem_limit_mb, mem_percent=s.mem_percent,
            net_rx_mb=s.net_rx_mb, net_tx_mb=s.net_tx_mb, pids=s.pids,
        )
        for s in samples
    ]
    return AppComputeResponse(
        project=project,
        samples=out,
        cpu_percent=round(sum(s.cpu_percent for s in out), 2),
        mem_used_mb=round(sum(s.mem_used_mb for s in out), 2),
    )


def _deployment_status(deployment) -> DeploymentStatus:
    return DeploymentStatus(
        id=deployment.id, project=deployment.project, status=deployment.status,
        source="app" if deployment.builder == "app" else "git",
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


@router.get("/deploys/{deployment_id}/explain", response_model=BuildDiagnosis)
async def api_explain_deploy(
    deployment_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> BuildDiagnosis:
    """Diagnose why a deployment's build/run turned out the way it did.

    Always runs the offline heuristic analyzer; enriches with the Anthropic API when
    ANTHROPIC_API_KEY is configured (best-effort, falls back to the heuristic)."""
    service = DeploysService(request)
    deployment = await service.get_deployment_for_tenant(
        session, current_admin.tenant_id, deployment_id
    )
    if deployment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found.")
    diagnosis = await service.diagnose_deployment(deployment)
    return BuildDiagnosis(
        deployment_id=deployment_id,
        status=deployment.status,
        **diagnosis.to_dict(),
    )


@router.get("/deploys/{deployment_id}/logs/stream")
async def api_stream_deploy_logs(
    deployment_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> StreamingResponse:
    """Live SSE build-log stream for a native (Tetra Engine) deployment.

    Validates tenant access up front (the request DB session is not safely usable
    inside the long-lived generator), then streams status/log/done events.
    """
    service = DeploysService(request)
    deployment = await service.get_deployment_for_tenant(session, current_admin.tenant_id, deployment_id)
    if deployment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found.")
    return StreamingResponse(
        service.stream_logs(current_admin.tenant_id, deployment_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/deploys/{deployment_id}/rollback", response_model=DeployStartResponse)
async def api_rollback_deploy(
    deployment_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> DeployStartResponse:
    """Instant rollback: redeploy a prior successful deployment's image (no rebuild)."""
    service = DeploysService(request)
    try:
        new_id = await service.rollback_for_tenant(current_admin.tenant_id, deployment_id)
    except (ProviderAPIError, DockerEngineError, BuildError) as exc:
        raise _engine_exc_to_http(exc) from exc
    return DeployStartResponse(deployment_id=new_id)


# ── Own infrastructure (Hetzner Cloud, platform-admin only) ───────────────
# Mailcow recommends >= 6GB RAM; a dedicated mail host defaults to an 8GB box.
MAIL_HOST_SERVER_TYPE = "cx32"


def _hetzner(request: Request) -> HetznerClient:
    return HetznerClient.from_settings(
        http_client=request.app.state.http_client, cache=request.app.state.cache
    )


def _infra_summary(server) -> InfraServerSummary:
    return InfraServerSummary(
        id=server.id, name=server.name, status=server.status, server_type=server.server_type,
        ipv4=server.ipv4, location=server.location, created=server.created,
    )


@router.get("/infra/servers", response_model=list[InfraServerSummary])
async def api_infra_servers(
    request: Request,
    _: AdminUser = Depends(require_platform_admin),
) -> list[InfraServerSummary]:
    client = _hetzner(request)
    if not client.is_configured():
        return []
    try:
        servers = await client.list_servers()
    except ProviderAPIError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=str(exc)) from exc
    return [_infra_summary(s) for s in servers]


@router.post("/infra/servers", response_model=InfraServerCreated)
async def api_infra_provision(
    payload: InfraServerCreateRequest,
    request: Request,
    _: AdminUser = Depends(require_platform_admin),
) -> InfraServerCreated:
    """Provision a Hetzner server (billable!) with a cloud-init bootstrap.

    ``role="docker"`` (default) brings up bare Docker; ``role="mail"`` stands up a
    dedicated Mailcow host (requires ``mail_hostname``, defaults to an 8GB box) —
    the automated form of ``scripts/install-mailcow.sh``.

    cloud-init is fire-and-forget: the returned action covers VM creation only; the
    bootstrap (Docker, or the ~15-min Mailcow install) continues after boot and must
    be confirmed before use. For mail, then create an API key in the Mailcow UI and
    set ``MAILCOW_URL`` / ``MAILCOW_API_KEY`` to activate the mail surface.
    """
    settings = get_settings()
    if not settings.enable_provider_actions:
        raise HTTPException(status_code=403, detail="Provider actions are disabled.")
    client = _hetzner(request)
    if not client.is_configured():
        raise HTTPException(status_code=503, detail="Hetzner is not configured (HETZNER_API_TOKEN).")
    role = (payload.role or "docker").strip().lower()
    if role not in {"docker", "mail"}:
        raise HTTPException(status_code=422, detail="role must be 'docker' or 'mail'.")
    if role == "mail":
        mail_hostname = payload.mail_hostname.strip().lower()
        # Mailcow needs a real FQDN (MX target) and >= 6GB RAM — default to an 8GB box.
        if not mail_hostname or mail_hostname.count(".") < 2:
            raise HTTPException(
                status_code=422,
                detail="role 'mail' requires a FQDN mail_hostname like mail.example.com.",
            )
        user_data = mailcow_cloud_init(mail_hostname)
        default_server_type = MAIL_HOST_SERVER_TYPE
    else:
        user_data = DEFAULT_CLOUD_INIT
        default_server_type = settings.hetzner_server_type
    try:
        result = await client.create_server(
            name=payload.name.strip(),
            server_type=payload.server_type or default_server_type,
            image=payload.image or settings.hetzner_image,
            location=payload.location or settings.hetzner_location,
            user_data=user_data,
            labels={"managed-by": "tetra", "role": role},
        )
    except ProviderAPIError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=str(exc)) from exc
    server_item = result.get("server") or {}
    action = result.get("action") or {}
    action_status = str(action.get("status") or "")
    if action.get("id"):
        action_status = await client.wait_action(int(action["id"]), max_seconds=120.0)
    return InfraServerCreated(
        server=_infra_summary(normalize_server(server_item)),
        action_status=action_status,
        root_password=str(result.get("root_password") or ""),
    )


@router.delete("/infra/servers/{server_id}")
async def api_infra_destroy(
    server_id: int,
    request: Request,
    _: AdminUser = Depends(require_platform_admin),
) -> dict[str, bool]:
    if not get_settings().enable_provider_actions:
        raise HTTPException(status_code=403, detail="Provider actions are disabled.")
    client = _hetzner(request)
    if not client.is_configured():
        raise HTTPException(status_code=503, detail="Hetzner is not configured (HETZNER_API_TOKEN).")
    try:
        await client.delete_server(server_id)
    except ProviderAPIError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=str(exc)) from exc
    return {"ok": True}


# ── Custom domains (verified via DNS TXT; routed at the edge) ──────────────
def _domains_service(request: Request) -> DomainsService:
    """DomainsService with the Cloudflare client attached (SaaS TLS, ADR 0009)."""
    cf = CloudflareClient.from_settings(
        http_client=request.app.state.http_client, cache=request.app.state.cache
    )
    return DomainsService(cf_client=cf)


def _domain_summary(service: DomainsService, domain) -> DomainSummary:
    info = service.instructions(domain)
    return DomainSummary(
        id=domain.id, project=domain.project, hostname=domain.hostname, status=domain.status,
        txt_name=info["txt_name"], txt_value=info["txt_value"], cname_target=info["cname_target"],
    )


@router.post("/domains", response_model=DomainSummary)
async def api_add_domain(
    payload: DomainRequest,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> DomainSummary:
    service = DomainsService()
    try:
        domain = await service.add_for_tenant(
            session, current_admin.tenant_id, project=payload.project, hostname=payload.hostname
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except DockerEngineError as exc:
        raise _engine_exc_to_http(exc) from exc
    return _domain_summary(service, domain)


@router.get("/domains", response_model=list[DomainSummary])
async def api_list_domains(
    project: str | None = None,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> list[DomainSummary]:
    service = DomainsService()
    domains = await service.list_for_tenant(session, current_admin.tenant_id, project)
    return [_domain_summary(service, d) for d in domains]


@router.post("/domains/{domain_id}/verify", response_model=DomainSummary)
async def api_verify_domain(
    domain_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> DomainSummary:
    service = _domains_service(request)
    try:
        domain = await service.verify_for_tenant(session, current_admin.tenant_id, domain_id)
    except DockerEngineError as exc:
        raise _engine_exc_to_http(exc) from exc
    return _domain_summary(service, domain)


@router.delete("/domains/{domain_id}")
async def api_delete_domain(
    domain_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> dict[str, bool]:
    removed = await _domains_service(request).delete_for_tenant(
        session, current_admin.tenant_id, domain_id
    )
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found.")
    return {"ok": True}


@router.get("/edge/ask")
async def api_edge_ask(
    domain: str = "",
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, bool]:
    """Caddy On-Demand TLS 'ask' endpoint — unauthenticated by design (Caddy is the
    caller); answers 200 only for a verified tenant domain, else 404. No data leaks."""
    if await DomainsService().is_hostname_verified(session, domain):
        return {"ok": True}
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown domain.")


def _env_summary(row) -> AppEnvVarSummary:
    """Mask secret values on read; non-secret values are returned decrypted."""
    return AppEnvVarSummary(
        key=row.key,
        value="••••••" if row.is_secret else decrypt(row.value),
        is_secret=row.is_secret,
        is_build_time=row.is_build_time,
    )


@router.get("/deploys/{project}/env", response_model=list[AppEnvVarSummary])
async def api_list_deploy_env(
    project: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> list[AppEnvVarSummary]:
    service = DeploysService(request)
    rows = await service.list_env_for_tenant(session, current_admin.tenant_id, project)
    return [_env_summary(row) for row in rows]


@router.post("/deploys/{project}/env", response_model=list[AppEnvVarSummary])
async def api_set_deploy_env(
    project: str,
    payload: AppEnvVarRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> list[AppEnvVarSummary]:
    key = payload.key.strip()
    if not key:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Env var key is required.")
    service = DeploysService(request)
    await service.set_env_for_tenant(
        session, current_admin.tenant_id, project,
        key=key, value=payload.value, is_secret=payload.is_secret, is_build_time=payload.is_build_time,
    )
    rows = await service.list_env_for_tenant(session, current_admin.tenant_id, project)
    return [_env_summary(row) for row in rows]


@router.delete("/deploys/{project}/env/{key}")
async def api_delete_deploy_env(
    project: str,
    key: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> dict[str, bool]:
    service = DeploysService(request)
    removed = await service.delete_env_for_tenant(session, current_admin.tenant_id, project, key)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Env var not found.")
    return {"ok": True}


# ── GitHub push-to-deploy webhooks ─────────────────────────────────────────
# NB: management routes live under /deploy-hooks (not /deploys/hooks) so they are not
# shadowed by the GET /deploys/{deployment_id} catch-all declared earlier.
@router.post("/deploy-hooks", response_model=DeployHookCreated)
async def api_create_deploy_hook(
    payload: DeployHookRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> DeployHookCreated:
    service = DeploysService(request)
    hook, secret = await service.create_hook_for_tenant(
        session, current_admin.tenant_id, payload.project,
        git_url=payload.git_url, ref=payload.ref, port=payload.port, previews=payload.previews,
    )
    base = str(request.base_url).rstrip("/")
    return DeployHookCreated(
        id=hook.id, project=hook.project, ref=hook.ref, secret=secret,
        url=f"{base}/api/v1/webhooks/github/{hook.id}",
    )


@router.get("/deploy-hooks", response_model=list[DeployHookSummary])
async def api_list_deploy_hooks(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> list[DeployHookSummary]:
    service = DeploysService(request)
    hooks = await service.list_hooks_for_tenant(session, current_admin.tenant_id)
    return [
        DeployHookSummary(
            id=h.id, project=h.project, git_url=h.git_url, ref=h.ref, port=h.port,
            enabled=h.enabled, previews=h.previews,
        )
        for h in hooks
    ]


@router.delete("/deploy-hooks/{hook_id}")
async def api_delete_deploy_hook(
    hook_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> dict[str, bool]:
    service = DeploysService(request)
    removed = await service.delete_hook_for_tenant(session, current_admin.tenant_id, hook_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found.")
    return {"ok": True}


@router.post("/webhooks/github/{hook_id}")
async def api_github_webhook(
    hook_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> JSONResponse:
    """Unauthenticated GitHub webhook receiver — authenticity is proven by the HMAC
    signature, not a session. A push to the hook's branch redeploys its app."""
    service = DeploysService(request)
    hook = await service.get_hook(session, hook_id)
    if hook is None or not hook.enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found.")

    body = await request.body()
    secret = decrypt(hook.secret)
    if not verify_signature(secret, body, request.headers.get("X-Hub-Signature-256")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature.")

    event = request.headers.get("X-GitHub-Event", "")
    if event == "ping":
        return JSONResponse(status_code=200, content={"ok": True, "pong": True})
    if event not in {"push", "delete"}:
        return JSONResponse(status_code=200, content={"ok": True, "ignored": True, "event": event})

    try:
        payload = json.loads(body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON.") from exc

    # Branch deleted → tear down its preview (GitHub sends both a `delete` event and a
    # `push` with deleted=true; teardown is idempotent so handling both is safe).
    if event == "delete":
        if payload.get("ref_type") != "branch" or not hook.previews:
            return JSONResponse(status_code=200, content={"ok": True, "ignored": True})
        removed = await service.teardown_preview_for_branch(
            hook.tenant_id, hook.project, str(payload.get("ref") or "")
        )
        return JSONResponse(status_code=200, content={"ok": True, "preview_removed": removed})

    branch = branch_from_ref(push_ref(payload))
    if not branch:  # tag pushes and malformed refs
        return JSONResponse(status_code=200, content={"ok": True, "ignored": True})

    if branch == hook.ref:
        if payload.get("deleted"):
            return JSONResponse(status_code=200, content={"ok": True, "ignored": True})
        try:
            deployment_id = await service.redeploy_for_tenant(
                hook.tenant_id, git_url=hook.git_url, ref=hook.ref,
                project=hook.project, port=hook.port,
            )
        except (ProviderAPIError, DockerEngineError, BuildError) as exc:
            raise _engine_exc_to_http(exc) from exc
        return JSONResponse(status_code=202, content={"ok": True, "deployment_id": deployment_id})

    # Non-production branch → preview environment (when enabled on the hook).
    if not hook.previews:
        return JSONResponse(
            status_code=200,
            content={"ok": True, "ignored": True, "reason": f"branch '{branch}' != '{hook.ref}'"},
        )
    if payload.get("deleted"):
        removed = await service.teardown_preview_for_branch(hook.tenant_id, hook.project, branch)
        return JSONResponse(status_code=200, content={"ok": True, "preview_removed": removed})
    try:
        deployment_id, domain = await service.deploy_preview_for_tenant(
            hook.tenant_id, git_url=hook.git_url, branch=branch,
            project=hook.project, port=hook.port,
        )
    except (ProviderAPIError, DockerEngineError, BuildError) as exc:
        raise _engine_exc_to_http(exc) from exc
    return JSONResponse(
        status_code=202,
        content={"ok": True, "preview": True, "deployment_id": deployment_id, "domain": domain},
    )


@router.get("/previews", response_model=list[PreviewSummary])
async def api_list_previews(
    request: Request,
    project: str | None = None,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> list[PreviewSummary]:
    service = DeploysService(request)
    previews = await service.list_previews_for_tenant(
        session, current_admin.tenant_id, project=project
    )
    return [
        PreviewSummary(
            id=p.id, project=p.project, branch=p.branch, preview_project=p.preview_project,
            domain=p.domain, last_deployment_id=p.last_deployment_id,
        )
        for p in previews
    ]


@router.delete("/previews/{preview_id}")
async def api_delete_preview(
    preview_id: str,
    request: Request,
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> dict[str, bool]:
    service = DeploysService(request)
    try:
        removed = await service.delete_preview_for_tenant(current_admin.tenant_id, preview_id)
    except DockerEngineError as exc:
        raise _engine_exc_to_http(exc) from exc
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preview not found.")
    return {"ok": True}


@router.get("/admin/overview", response_model=PlatformOverview)
async def api_admin_overview(
    session: AsyncSession = Depends(get_db_session),
    _: AdminUser = Depends(require_platform_admin),
) -> PlatformOverview:
    """Aggregate platform state for the super-admin command center.

    Platform-admin only. Composes tenant status counts, headline totals, committed
    resource allocation, the pending-approval queue, and recent audit events into a
    single payload so the console renders the command center without fan-out.
    """
    # Tenant counts bucketed by lifecycle status (single grouped query).
    status_rows = (
        await session.execute(select(Tenant.status, func.count()).group_by(Tenant.status))
    ).all()
    status_map: dict[str, int] = {row[0]: row[1] for row in status_rows}
    tenant_status = TenantStatusCounts(
        active=status_map.get(TENANT_ACTIVE, 0),
        pending=status_map.get(TENANT_PENDING, 0),
        suspended=status_map.get(TENANT_SUSPENDED, 0),
        rejected=status_map.get(TENANT_REJECTED, 0),
        total=sum(status_map.values()),
    )

    # Resource counts bucketed by resource_type.
    resource_rows = (
        await session.execute(
            select(TenantResource.resource_type, func.count()).group_by(
                TenantResource.resource_type
            )
        )
    ).all()
    resource_map: dict[str, int] = {row[0]: row[1] for row in resource_rows}

    admins_total = await session.scalar(select(func.count()).select_from(AdminUser)) or 0
    plans_total = (
        await session.scalar(
            select(func.count()).select_from(Plan).where(Plan.is_archived.is_(False))
        )
        or 0
    )
    totals = PlatformTotals(
        tenants=tenant_status.total,
        admins=admins_total,
        apps=resource_map.get(RESOURCE_TYPE_APP, 0),
        databases=resource_map.get(RESOURCE_TYPE_DATABASE, 0),
        plans=plans_total,
    )

    # Committed resource allocation summed across every tenant resource.
    alloc = (
        await session.execute(
            select(
                func.coalesce(func.sum(TenantResource.cpu_millicores), 0),
                func.coalesce(func.sum(TenantResource.mem_mb), 0),
                func.coalesce(func.sum(TenantResource.disk_mb), 0),
            )
        )
    ).one()
    committed = PlatformResourceUsage(
        cpu_millicores=int(alloc[0] or 0),
        mem_mb=int(alloc[1] or 0),
        disk_mb=int(alloc[2] or 0),
    )

    # Pending-approval queue (oldest first), plan keys resolved in one extra query.
    pending = list(
        (
            await session.scalars(
                select(Tenant).where(Tenant.status == TENANT_PENDING).order_by(Tenant.created_at)
            )
        ).all()
    )
    plan_ids = {t.plan_id for t in pending if t.plan_id}
    plan_key_map: dict[str, str] = {}
    if plan_ids:
        plan_rows = list((await session.scalars(select(Plan).where(Plan.id.in_(plan_ids)))).all())
        plan_key_map = {p.id: p.key for p in plan_rows}
    pending_tenants = [
        _tenant_summary(t, plan_key_map.get(t.plan_id, "") if t.plan_id else "") for t in pending
    ]

    # Reseller revenue rolled up from the charge ledger + AI money across all tenants.
    from datetime import UTC, datetime, timedelta

    since = datetime.now(UTC) - timedelta(days=30)
    rev = (
        await session.execute(
            select(
                func.coalesce(func.sum(ResellerCharge.resale_price_cents), 0),
                func.coalesce(func.sum(ResellerCharge.margin_cents), 0),
                func.count(),
            )
        )
    ).one()
    resale_30d = await session.scalar(
        select(func.coalesce(func.sum(ResellerCharge.resale_price_cents), 0)).where(
            ResellerCharge.created_at >= since
        )
    ) or 0
    revenue = PlatformRevenue(
        resale_total_usd=int(rev[0] or 0) / 100,
        margin_total_usd=int(rev[1] or 0) / 100,
        resale_30d_usd=int(resale_30d) / 100,
        charges=int(rev[2] or 0),
    )

    credit_float = await session.scalar(
        select(func.coalesce(func.sum(TenantCredit.balance_micro_usd), 0))
    ) or 0
    ai_row = (
        await session.execute(
            select(
                func.coalesce(func.sum(AiUsageEvent.billed_micro_usd), 0),
                func.count(),
            ).where(AiUsageEvent.created_at >= since)
        )
    ).one()
    ai_summary = PlatformAiSummary(
        credit_float_usd=int(credit_float) / MICRO_USD_PER_USD,
        spend_30d_usd=int(ai_row[0] or 0) / MICRO_USD_PER_USD,
        requests_30d=int(ai_row[1] or 0),
    )

    # Most recent audit events across the whole platform.
    events = list(
        (
            await session.scalars(
                select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(20)
            )
        ).all()
    )

    return PlatformOverview(
        tenant_status=tenant_status,
        totals=totals,
        committed_resources=committed,
        revenue=revenue,
        ai=ai_summary,
        pending_tenants=pending_tenants,
        recent_events=[_audit_event_summary(e) for e in events],
    )


@router.get("/audit", response_model=AuditLogResponse)
async def api_audit_log(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    action: str = "",
    actor: str = "",
    session: AsyncSession = Depends(get_db_session),
    _: AdminUser = Depends(require_platform_admin),
) -> AuditLogResponse:
    """Filtered, paginated platform audit log (platform-admin only).

    Audit events are platform-global (no tenant scope), so this is a super-admin
    surface. Filters: substring match on ``action`` and/or ``actor`` email.
    """
    limit = max(1, min(limit, 200))
    offset = max(0, offset)

    conditions = []
    if action.strip():
        conditions.append(AuditEvent.action.ilike(f"%{action.strip()}%"))
    if actor.strip():
        conditions.append(AuditEvent.actor_email.ilike(f"%{actor.strip()}%"))

    rows_q = select(AuditEvent)
    count_q = select(func.count()).select_from(AuditEvent)
    for condition in conditions:
        rows_q = rows_q.where(condition)
        count_q = count_q.where(condition)

    total = await session.scalar(count_q) or 0
    rows = list(
        (
            await session.scalars(
                rows_q.order_by(AuditEvent.created_at.desc()).limit(limit).offset(offset)
            )
        ).all()
    )
    return AuditLogResponse(
        events=[_audit_event_summary(event) for event in rows],
        total=int(total),
        limit=limit,
        offset=offset,
    )


# ── Reseller: Cloudflare plans + services on tenant zones (Path A) ─────────
def _plan_summary(plan: dict) -> CloudflarePlanSummary:
    return CloudflarePlanSummary(
        id=str(plan.get("id") or ""),
        name=str(plan.get("name") or ""),
        price=float(plan.get("price") or 0),
        currency=str(plan.get("currency") or ""),
        frequency=str(plan.get("frequency") or ""),
        can_subscribe=bool(plan.get("can_subscribe")),
        is_subscribed=bool(plan.get("is_subscribed")),
    )


def _subscription_summary(sub: dict) -> ZoneSubscriptionSummary:
    rate_plan = sub.get("rate_plan") if isinstance(sub.get("rate_plan"), dict) else {}
    return ZoneSubscriptionSummary(
        id=str(sub.get("id") or ""),
        state=str(sub.get("state") or ""),
        price=float(sub.get("price") or 0),
        currency=str(sub.get("currency") or ""),
        frequency=str(sub.get("frequency") or ""),
        rate_plan_id=str((rate_plan or {}).get("id") or ""),
    )


@router.get("/cloudflare/services", response_model=list[ResellableServiceSummary])
async def api_cf_services(
    request: Request,
    _: AdminUser = Depends(get_current_api_admin),
) -> list[ResellableServiceSummary]:
    """The resellable Cloudflare catalog (plans + security/performance/developer services)."""
    return [
        ResellableServiceSummary(
            key=s.key, name=s.name, category=s.category, activation=s.activation,
            rate_plan=s.rate_plan, description=s.description,
        )
        for s in ResellerService(request).catalog()
    ]


@router.get("/cloudflare/zones/{zone_id}/plans", response_model=list[CloudflarePlanSummary])
async def api_cf_zone_plans(
    zone_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> list[CloudflarePlanSummary]:
    service = ResellerService(request)
    try:
        plans = await service.list_plans_for_tenant(session, current_admin.tenant_id, zone_id)
    except ResellerError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except ProviderAPIError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=str(exc)) from exc
    return [_plan_summary(p) for p in plans]


@router.get("/cloudflare/zones/{zone_id}/subscription", response_model=ZoneSubscriptionSummary)
async def api_cf_zone_subscription(
    zone_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> ZoneSubscriptionSummary:
    service = ResellerService(request)
    try:
        sub = await service.get_subscription_for_tenant(session, current_admin.tenant_id, zone_id)
    except ResellerError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return _subscription_summary(sub)


@router.post("/cloudflare/zones/{zone_id}/subscription", response_model=ZoneSubscriptionSummary)
async def api_cf_activate_plan(
    zone_id: str,
    payload: PlanActivateRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> ZoneSubscriptionSummary:
    """Activate/upgrade a tenant zone's paid Cloudflare plan (gated by provider actions)."""
    service = ResellerService(request)
    try:
        result = await service.activate_plan_for_tenant(
            session, current_admin.tenant_id, zone_id,
            payload.rate_plan_id, frequency=payload.frequency,
        )
    except ResellerError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except ProviderAPIError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=str(exc)) from exc
    return _subscription_summary(result)


@router.post(
    "/cloudflare/zones/{zone_id}/services/{service_key}/activate",
    response_model=ServiceActivateResponse,
)
async def api_cf_activate_service(
    zone_id: str,
    service_key: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> ServiceActivateResponse:
    """Activate a resellable Cloudflare service on a tenant zone (gated by provider actions)."""
    service = ResellerService(request)
    try:
        out = await service.activate_service_for_tenant(
            session, current_admin.tenant_id, zone_id, service_key
        )
    except ResellerError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except ProviderAPIError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=str(exc)) from exc
    return ServiceActivateResponse(
        service=str(out.get("service") or service_key),
        note=str(out.get("note") or ""),
        state=str((out.get("result") or {}).get("state") or ""),
    )


# ── Reseller: AI models (OpenRouter per-tenant runtime keys) ────────────────
def _ai_model_summary(model: dict) -> AiModelSummary:
    pricing = model.get("pricing") if isinstance(model.get("pricing"), dict) else {}
    return AiModelSummary(
        id=str(model.get("id") or ""),
        name=str(model.get("name") or ""),
        context_length=int(model.get("context_length") or 0),
        prompt_price=str((pricing or {}).get("prompt") or ""),
        completion_price=str((pricing or {}).get("completion") or ""),
    )


def _ai_key_summary(data: dict) -> AiKeySummary:
    return AiKeySummary(
        hash=str(data.get("hash") or ""),
        label=str(data.get("label") or ""),
        name=str(data.get("name") or ""),
        limit=data.get("limit"),
        usage=float(data.get("usage") or 0),
        disabled=bool(data.get("disabled")),
    )


@router.get("/ai/models", response_model=list[AiModelSummary])
async def api_ai_models(
    request: Request,
    _: AdminUser = Depends(get_current_api_admin),
) -> list[AiModelSummary]:
    """The resellable OpenRouter model catalog."""
    try:
        models = await AiResellerService(request).list_models()
    except ProviderAPIError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=str(exc)) from exc
    return [_ai_model_summary(m) for m in models]


@router.get("/ai/keys", response_model=list[AiKeySummary])
async def api_ai_keys(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> list[AiKeySummary]:
    keys = await AiResellerService(request).list_keys_for_tenant(session, current_admin.tenant_id)
    return [_ai_key_summary(k) for k in keys]


@router.post("/ai/keys", response_model=AiKeyCreated)
async def api_ai_provision_key(
    payload: AiKeyProvisionRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> AiKeyCreated:
    """Provision a per-tenant OpenRouter runtime key (secret returned once)."""
    service = AiResellerService(request)
    try:
        out = await service.provision_key_for_tenant(
            session, current_admin.tenant_id,
            label=payload.label, limit=payload.limit, limit_reset=payload.limit_reset,
        )
    except ResellerError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except ProviderAPIError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=str(exc)) from exc
    return AiKeyCreated(
        key=str(out.get("key") or ""), hash=str(out.get("hash") or ""),
        label=str(out.get("label") or ""), limit=out.get("limit"),
    )


@router.patch("/ai/keys/{key_hash}", response_model=AiKeySummary)
async def api_ai_update_key(
    key_hash: str,
    payload: AiKeyUpdateRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> AiKeySummary:
    service = AiResellerService(request)
    try:
        data = await service.update_key_for_tenant(
            session, current_admin.tenant_id, key_hash,
            limit=payload.limit, disabled=payload.disabled,
        )
    except ResellerError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except ProviderAPIError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=str(exc)) from exc
    return _ai_key_summary(data)


@router.delete("/ai/keys/{key_hash}")
async def api_ai_revoke_key(
    key_hash: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> dict[str, bool]:
    service = AiResellerService(request)
    try:
        await service.revoke_key_for_tenant(session, current_admin.tenant_id, key_hash)
    except ResellerError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except ProviderAPIError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=str(exc)) from exc
    return {"ok": True}


# ── AI gateway: metered shared-key chat (Model A) + prepaid credit wallet ──
@router.get("/ai/status", response_model=AiStatusResponse)
async def api_ai_status(
    request: Request,
    _: AdminUser = Depends(get_current_api_admin),
) -> AiStatusResponse:
    """Which AI billing mode is live + the shared gateway key's remaining balance."""
    service = AiResellerService(request)
    credits = await service.platform_credits()
    total = float(credits.get("total_credits", 0) or 0)
    used = float(credits.get("total_usage", 0) or 0)
    return AiStatusResponse(
        mode=service.mode(),
        configured=service.mode() != "disabled",
        platform_credit_usd=max(0.0, total - used),
        platform_used_usd=used,
    )


@router.post("/ai/chat", response_model=AiChatResponse)
async def api_ai_chat(
    payload: AiChatRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> AiChatResponse:
    """Gateway chat completion, metered into the tenant's prepaid credit wallet."""
    service = AiResellerService(request)
    body = payload.model_dump(exclude_none=True)
    try:
        out = await service.chat_for_tenant(session, current_admin.tenant_id, body=body)
    except ResellerError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except ProviderAPIError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=str(exc)) from exc
    return AiChatResponse(
        completion=out.get("completion", {}),
        usage=AiChatUsage(**out.get("usage", {})),
        balance_usd=float(out.get("balance_usd", 0.0)),
    )


@router.get("/ai/usage", response_model=AiUsageReport)
async def api_ai_usage(
    request: Request,
    days: int = 30,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> AiUsageReport:
    """Per-tenant AI spend: totals, per-model breakdown, and recent metered calls."""
    data = await AiResellerService(request).usage_for_tenant(
        session, current_admin.tenant_id, days=max(1, min(days, 365))
    )
    return AiUsageReport(
        total_billed_usd=data["total_billed_usd"],
        total_cost_usd=data["total_cost_usd"],
        total_requests=data["total_requests"],
        by_model=data["by_model"],
        events=[AiUsageEventSummary(**e) for e in data["events"]],
    )


def _credit_balance_response(balance_micro: int, txns) -> CreditBalanceResponse:
    return CreditBalanceResponse(
        balance_usd=balance_micro / MICRO_USD_PER_USD,
        transactions=[
            CreditTransactionSummary(
                kind=t.kind, amount_usd=t.delta_micro_usd / MICRO_USD_PER_USD,
                reference=t.reference, created_at=t.created_at.isoformat() if t.created_at else "",
            )
            for t in txns
        ],
    )


@router.get("/billing/credits", response_model=CreditBalanceResponse)
async def api_billing_credits(
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> CreditBalanceResponse:
    """The caller tenant's prepaid AI credit balance + recent wallet transactions."""
    svc = CreditService(session)
    tenant_id = current_admin.tenant_id or ""
    return _credit_balance_response(await svc.balance(tenant_id), await svc.transactions(tenant_id))


@router.get("/billing/credits/overview", response_model=list[TenantCreditOverview])
async def api_billing_credits_overview(
    session: AsyncSession = Depends(get_db_session),
    _: AdminUser = Depends(require_platform_admin),
) -> list[TenantCreditOverview]:
    """Platform-admin: every tenant's AI credit balance + 30-day spend."""
    rows = await CreditService(session).overview()
    return [TenantCreditOverview(**r) for r in rows]


@router.post("/billing/credits", response_model=CreditBalanceResponse)
async def api_billing_topup(
    payload: CreditTopupRequest,
    session: AsyncSession = Depends(get_db_session),
    _: AdminUser = Depends(require_platform_admin),
) -> CreditBalanceResponse:
    """Platform-admin: add prepaid AI credit to a tenant's wallet (after payment)."""
    svc = CreditService(session)
    await svc.topup(
        payload.tenant_id, round(payload.amount_usd * MICRO_USD_PER_USD), reference="admin top-up"
    )
    return _credit_balance_response(
        await svc.balance(payload.tenant_id), await svc.transactions(payload.tenant_id)
    )


# ── Reseller billing: pricing rules + charge ledger (slice 1) ──────────────
def _pricing_rule_summary(rule) -> PricingRuleSummary:
    return PricingRuleSummary(
        offering_key=rule.offering_key, provider=rule.provider, cost_shape=rule.cost_shape,
        wholesale_cost_cents=rule.wholesale_cost_cents, unit=rule.unit,
        rule=rule.rule, rule_value=rule.rule_value,
        resale_price_cents=compute_resale_cents(rule.wholesale_cost_cents, rule.rule, rule.rule_value),
    )


def _charge_summary(charge) -> ResellerChargeSummary:
    return ResellerChargeSummary(
        id=charge.id, tenant_id=charge.tenant_id, offering_key=charge.offering_key,
        provider=charge.provider, wholesale_cost_cents=charge.wholesale_cost_cents,
        resale_price_cents=charge.resale_price_cents, margin_cents=charge.margin_cents,
        status=charge.status, created_at=charge.created_at.isoformat() if charge.created_at else "",
    )


@router.get("/billing/pricing", response_model=list[PricingRuleSummary])
async def api_billing_pricing(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    _: AdminUser = Depends(require_platform_admin),
) -> list[PricingRuleSummary]:
    service = BillingService(session, request.state.settings)
    return [_pricing_rule_summary(r) for r in await service.list_rules()]


@router.put("/billing/pricing/{offering_key}", response_model=PricingRuleSummary)
async def api_billing_set_pricing(
    offering_key: str,
    payload: PricingRuleRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    _: AdminUser = Depends(require_platform_admin),
) -> PricingRuleSummary:
    """Set/replace the pricing rule for an offering (platform-admin)."""
    service = BillingService(session, request.state.settings)
    rule = await service.set_rule(
        offering_key, provider=payload.provider, cost_shape=payload.cost_shape,
        wholesale_cost_cents=payload.wholesale_cost_cents, unit=payload.unit,
        rule=payload.rule, rule_value=payload.rule_value,
    )
    return _pricing_rule_summary(rule)


@router.get("/billing/quote/{offering_key}", response_model=PriceQuote)
async def api_billing_quote(
    offering_key: str,
    request: Request,
    wholesale_cents: int | None = None,
    session: AsyncSession = Depends(get_db_session),
    _: AdminUser = Depends(get_current_api_admin),
) -> PriceQuote:
    """Resolve the resale price for an offering (its rule, else the platform default markup)."""
    service = BillingService(session, request.state.settings)
    try:
        quote = await service.quote(offering_key, wholesale_cents=wholesale_cents)
    except BillingError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return PriceQuote(**quote)


@router.get("/billing/charges", response_model=list[ResellerChargeSummary])
async def api_billing_charges(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> list[ResellerChargeSummary]:
    """The reseller charge ledger — platform-admins see all tenants; others see their own."""
    service = BillingService(session, request.state.settings)
    tenant_scope = None if current_admin.role == ROLE_PLATFORM_ADMIN else current_admin.tenant_id
    return [_charge_summary(c) for c in await service.list_charges(tenant_id=tenant_scope)]


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


# ---------------------------------------------------------------------------
# Usage endpoint  (/api/v1/usage)
# ---------------------------------------------------------------------------

async def _resolve_plan_for_tenant(session: AsyncSession, tenant_id: str) -> Plan | None:
    """Return the Plan for the tenant, falling back to the free plan, then None."""
    tenant = await session.get(Tenant, tenant_id)
    plan: Plan | None = None
    if tenant and tenant.plan_id:
        plan = await session.get(Plan, tenant.plan_id)
    if plan is None:
        plan = await session.scalar(select(Plan).where(Plan.key == "free"))
    return plan


@router.get("/usage", response_model=UsageResponse)
async def api_usage(
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> UsageResponse:
    """Return the calling tenant's quota usage versus their plan limits.

    Accessible by any authenticated admin for their own tenant — not gated to
    platform-admin.  Only ``apps`` is enforced; cpu/mem/disk/domains are advisory.
    """
    tenant_id = current_admin.tenant_id

    # --- usage from QuotaService ---
    quota_svc = QuotaService(session, tenant_id)
    used = await quota_svc.usage()

    # --- plan limits ---
    plan = await _resolve_plan_for_tenant(session, tenant_id)
    if plan is not None:
        plan_key = plan.key
        apps_limit = plan.max_apps
        cpu_limit = plan.cpu_millicores
        mem_limit = plan.mem_mb
        disk_limit = plan.disk_mb
        domains_limit = plan.max_domains
    else:
        # Absolute fallback — no plan row at all.
        from app.services.quota import DEFAULT_FREE_MAX_APPS
        plan_key = ""
        apps_limit = DEFAULT_FREE_MAX_APPS
        cpu_limit = 0
        mem_limit = 0
        disk_limit = 0
        domains_limit = 0

    # --- domains used: count DNS-zone TenantResource rows ---
    domains_used: int = (
        await session.scalar(
            select(func.count()).select_from(TenantResource).where(
                TenantResource.tenant_id == tenant_id,
                TenantResource.resource_type == RESOURCE_TYPE_DNS_ZONE,
            )
        )
    ) or 0

    return UsageResponse(
        plan_key=plan_key,
        apps_used=used["apps"],
        apps_limit=apps_limit,
        cpu_millicores_used=used["cpu_millicores"],
        cpu_millicores_limit=cpu_limit,
        mem_mb_used=used["mem_mb"],
        mem_mb_limit=mem_limit,
        disk_mb_used=used["disk_mb"],
        disk_mb_limit=disk_limit,
        domains_used=domains_used,
        domains_limit=domains_limit,
        enforced=["apps"],
    )


# ---------------------------------------------------------------------------
# Databases endpoints  (/api/v1/databases)
# ---------------------------------------------------------------------------


@router.get("/databases", response_model=list[DatabaseSummary])
async def api_list_databases(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> list[DatabaseSummary]:
    """List Coolify databases assigned to the caller's tenant."""
    service = DatabasesService(request)
    databases = await service.list_databases_for_tenant(
        session,
        current_admin.tenant_id,
        refresh=request.query_params.get("refresh") == "1",
    )
    return [
        DatabaseSummary(
            id=db.id,
            name=db.name,
            type=db.type,
            status=db.status,
            internal_db_url=db.internal_db_url,
            image=db.image,
        )
        for db in databases
    ]


@router.get("/databases/targets", response_model=DatabaseTargets)
async def api_database_targets(
    request: Request,
    _: AdminUser = Depends(get_current_api_admin),
) -> DatabaseTargets:
    """Coolify servers + projects to populate the provisioning form's pickers."""
    data = await DatabasesService(request).list_targets()
    return DatabaseTargets(
        servers=[DatabaseTargetOption(**s) for s in data["servers"]],
        projects=[DatabaseTargetOption(**p) for p in data["projects"]],
    )


@router.post("/databases", response_model=ActionResponse)
async def api_provision_database(
    payload: DatabaseProvisionRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> ActionResponse:
    """Provision a new managed database via Coolify (tenant-scoped).

    Gated by ENABLE_PROVIDER_ACTIONS. db_type must be in the supported allow-list.
    """
    service = DatabasesService(request)
    try:
        result = await service.provision_for_tenant(
            session,
            current_admin.tenant_id,
            db_type=payload.db_type,
            name=payload.name,
            server_uuid=payload.server_uuid,
            project_uuid=payload.project_uuid,
            environment_name=payload.environment_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except ProviderAPIError as exc:
        _status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=_status_code, detail=str(exc)) from exc
    return ActionResponse(
        ok=bool(result.get("ok", True)),
        message=str(result.get("message", "Database provisioned.")),
    )


@router.get("/databases/{db_uuid}/backups", response_model=list[BackupConfigSummary])
async def api_list_database_backups(
    db_uuid: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> list[BackupConfigSummary]:
    """List backup configs for a tenant-owned database."""
    service = DatabasesService(request)
    try:
        backups = await service.backups_for_tenant(session, current_admin.tenant_id, db_uuid)
    except ProviderAPIError as exc:
        _status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=_status_code, detail=str(exc)) from exc
    return [
        BackupConfigSummary(
            id=str(b.get("uuid") or b.get("id") or ""),
            frequency=str(b.get("frequency") or ""),
            retention_days=int(b.get("retention_days") or b.get("retention") or 0),
            s3_storage_id=str(b.get("s3_storage_id") or ""),
        )
        for b in backups
    ]


@router.post("/databases/{db_uuid}/backups", response_model=ActionResponse)
async def api_create_database_backup(
    db_uuid: str,
    payload: BackupCreateRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> ActionResponse:
    """Create a backup config for a tenant-owned database. Gated by ENABLE_PROVIDER_ACTIONS."""
    service = DatabasesService(request)
    config: dict[str, object] = {
        "frequency": payload.frequency,
        "retention_days": payload.retention_days,
    }
    if payload.s3_storage_id:
        config["s3_storage_id"] = payload.s3_storage_id
    try:
        result = await service.create_backup_for_tenant(
            session, current_admin.tenant_id, db_uuid, **config
        )
    except ProviderAPIError as exc:
        _status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=_status_code, detail=str(exc)) from exc
    return ActionResponse(
        ok=bool(result.get("ok", True)),
        message=str(result.get("message", "Backup config created.")),
    )


# ── Object storage: resell Cloudflare R2 buckets ───────────────────────────
@router.get("/storage/status", response_model=StorageStatusResponse)
async def api_storage_status(
    request: Request,
    _: AdminUser = Depends(get_current_api_admin),
) -> StorageStatusResponse:
    service = StorageService(request)
    return StorageStatusResponse(
        configured=service.is_configured(),
        can_issue_credentials=service.client.can_issue_credentials(),
        endpoint=service.client.s3_endpoint if service.is_configured() else "",
    )


@router.get("/storage/buckets", response_model=list[BucketSummary])
async def api_list_buckets(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> list[BucketSummary]:
    rows = await StorageService(request).list_buckets_for_tenant(session, current_admin.tenant_id)
    return [BucketSummary(**r) for r in rows]


@router.post("/storage/buckets", response_model=BucketCreated)
async def api_provision_bucket(
    payload: BucketProvisionRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> BucketCreated:
    """Provision a tenant R2 bucket; S3 credentials (if configured) are returned ONCE."""
    service = StorageService(request)
    try:
        out = await service.provision_bucket_for_tenant(
            session, current_admin.tenant_id, name=payload.name
        )
    except ResellerError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except ProviderAPIError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=str(exc)) from exc
    return BucketCreated(**out)


@router.delete("/storage/buckets/{name}")
async def api_delete_bucket(
    name: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> dict[str, bool]:
    service = StorageService(request)
    try:
        await service.delete_bucket_for_tenant(session, current_admin.tenant_id, name)
    except ResellerError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except ProviderAPIError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=str(exc)) from exc
    return {"ok": True}


# ── Scheduled jobs (cron-triggered HTTP, run by the in-process scheduler) ───
def _job_summary(job) -> ScheduledJobSummary:
    return ScheduledJobSummary(
        id=job.id, name=job.name, cron=job.cron, url=job.url, method=job.method,
        enabled=job.enabled,
        last_run_at=job.last_run_at.isoformat() if job.last_run_at else "",
        last_status=job.last_status, last_detail=job.last_detail,
    )


@router.get("/jobs", response_model=list[ScheduledJobSummary])
async def api_list_jobs(
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> list[ScheduledJobSummary]:
    jobs = await JobsService(session).list_for_tenant(current_admin.tenant_id)
    return [_job_summary(j) for j in jobs]


@router.post("/jobs", response_model=ScheduledJobSummary)
async def api_create_job(
    payload: JobCreateRequest,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> ScheduledJobSummary:
    try:
        job = await JobsService(session).create(
            current_admin.tenant_id,
            name=payload.name, cron=payload.cron, url=payload.url, method=payload.method,
        )
    except JobError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return _job_summary(job)


@router.patch("/jobs/{job_id}", response_model=ScheduledJobSummary)
async def api_update_job(
    job_id: str,
    payload: JobUpdateRequest,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> ScheduledJobSummary:
    try:
        job = await JobsService(session).update(
            current_admin.tenant_id, job_id,
            cron=payload.cron, url=payload.url, method=payload.method, enabled=payload.enabled,
        )
    except JobError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return _job_summary(job)


@router.delete("/jobs/{job_id}")
async def api_delete_job(
    job_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> dict[str, bool]:
    try:
        await JobsService(session).delete(current_admin.tenant_id, job_id)
    except JobError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return {"ok": True}


@router.get("/jobs/{job_id}/runs", response_model=list[JobRunSummary])
async def api_job_runs(
    job_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> list[JobRunSummary]:
    try:
        runs = await JobsService(session).list_runs(current_admin.tenant_id, job_id)
    except JobError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return [
        JobRunSummary(
            status=r.status, detail=r.detail, duration_ms=r.duration_ms,
            started_at=r.started_at.isoformat() if r.started_at else "",
        )
        for r in runs
    ]


# ── Team / RBAC ──────────────────────────────────────────────────────────────
def _team_member_summary(m: AdminUser) -> TeamMemberSummary:
    return TeamMemberSummary(
        id=m.id,
        email=m.email,
        full_name=m.full_name,
        role=m.role,
        is_active=m.is_active,
        last_login_at=m.last_login_at.isoformat() if m.last_login_at else "",
        created_at=m.created_at.isoformat() if m.created_at else "",
    )


def _team_invite_summary(i) -> TeamInviteSummary:
    return TeamInviteSummary(
        id=i.id,
        email=i.email,
        role=i.role,
        status=i.status,
        created_at=i.created_at.isoformat() if i.created_at else "",
        expires_at=i.expires_at.isoformat() if i.expires_at else "",
    )


@router.get("/team", response_model=TeamResponse)
async def api_team(
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> TeamResponse:
    service = TeamService(session)
    members = await service.list_members(current_admin.tenant_id)
    invites = await service.list_invites(current_admin.tenant_id)
    return TeamResponse(
        members=[_team_member_summary(m) for m in members],
        invites=[_team_invite_summary(i) for i in invites],
    )


@router.post("/team/invites", response_model=InviteCreateResponse)
async def api_create_invite(
    payload: InviteCreateRequest,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(require_tenant_owner),
) -> InviteCreateResponse:
    try:
        invite, raw_token = await TeamService(session).create_invite(
            current_admin.tenant_id, current_admin, payload.email, payload.role
        )
    except TeamError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    # Relative path — the console prepends its own origin to build the share URL.
    return InviteCreateResponse(
        invite=_team_invite_summary(invite),
        token=raw_token,
        accept_url=f"/auth/accept-invite?token={raw_token}",
    )


@router.delete("/team/invites/{invite_id}")
async def api_revoke_invite(
    invite_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(require_tenant_owner),
) -> dict[str, bool]:
    try:
        await TeamService(session).revoke_invite(current_admin.tenant_id, invite_id)
    except TeamError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return {"ok": True}


@router.post("/team/members/{member_id}/role", response_model=TeamMemberSummary)
async def api_change_member_role(
    member_id: str,
    payload: RoleChangeRequest,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(require_tenant_owner),
) -> TeamMemberSummary:
    try:
        member = await TeamService(session).change_role(
            current_admin.tenant_id, member_id, payload.role
        )
    except TeamError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return _team_member_summary(member)


@router.delete("/team/members/{member_id}", response_model=TeamMemberSummary)
async def api_remove_member(
    member_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(require_tenant_owner),
) -> TeamMemberSummary:
    try:
        member = await TeamService(session).remove_member(
            current_admin.tenant_id, member_id, current_admin
        )
    except TeamError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return _team_member_summary(member)


@router.get("/auth/invite", response_model=InvitePreviewResponse)
async def api_preview_invite(
    token: str,
    session: AsyncSession = Depends(get_db_session),
) -> InvitePreviewResponse:
    """Public — resolve a redeemable invite so the accept page can show who/what
    it's for. 404 for unknown/expired/used tokens (no information leak)."""
    invite = await TeamService(session).peek_invite(token)
    if invite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite is invalid or expired.")
    tenant = await session.get(Tenant, invite.tenant_id)
    return InvitePreviewResponse(
        tenant_name=tenant.name if tenant else "",
        email=invite.email,
        role=invite.role,
    )


@router.post("/auth/accept-invite", response_model=AuthResponse)
async def api_accept_invite(
    request: Request,
    payload: AcceptInviteRequest,
    session: AsyncSession = Depends(get_db_session),
) -> AuthResponse:
    """Public — redeem an invite to create the teammate's login, then sign them in."""
    try:
        admin = await TeamService(session).accept_invite(
            payload.token, payload.full_name, payload.password
        )
    except TeamError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    token = create_api_token(request.state.settings, admin)
    return AuthResponse(token=token, admin=_admin_summary(admin))
