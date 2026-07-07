from pydantic import BaseModel, ConfigDict, Field


class SignupRequest(BaseModel):
    """Public signup payload — ONLY these three fields are accepted.

    Role, plan_id, status, tenant_id, and is_platform_scope are NEVER accepted
    from the client; the service sets them server-side.

    Field max_lengths turn oversized payloads into 422s (Pydantic) instead of
    DB-layer 500s. The password lower bound (>= 10 chars) is enforced server-side
    by validate_password; the Field bound here is only an upper cap.
    """

    email: str = Field(..., max_length=254)
    password: str = Field(..., max_length=200)
    org_name: str = Field(..., min_length=1, max_length=120)


class AdminSummary(BaseModel):
    id: str
    email: str
    full_name: str
    is_active: bool
    tenant_id: str
    tenant_slug: str
    tenant_name: str
    role: str = ""
    tenant_status: str = ""


class AuthResponse(BaseModel):
    token: str
    admin: AdminSummary


class AccountUpdateRequest(BaseModel):
    full_name: str
    email: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class ProviderSummary(BaseModel):
    name: str
    status: str
    detail: str


class DashboardMetrics(BaseModel):
    projects: int
    unhealthy_projects: int
    mail_domains: int
    dns_zones: int
    admins: int


class DashboardResponse(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=False)

    providers: list[ProviderSummary]
    metrics: DashboardMetrics


class ProjectSummary(BaseModel):
    id: str
    name: str
    status: str
    primary_domain: str
    repository: str
    environment: str
    updated_at: str
    healthcheck_enabled: bool


class ActionResponse(BaseModel):
    ok: bool = True
    message: str
    deployment_id: str = ""


class ProjectDeploymentSummary(BaseModel):
    id: str
    status: str
    created_at: str
    updated_at: str
    commit: str
    branch: str


class DeploymentLogLine(BaseModel):
    output: str
    type: str = "stdout"
    timestamp: str = ""


class DeploymentDetail(BaseModel):
    id: str
    status: str
    created_at: str
    updated_at: str
    commit: str
    branch: str
    log_lines: list[DeploymentLogLine] = []


class MailDomainSummary(BaseModel):
    domain_name: str
    mailboxes: int
    aliases: int
    quota_bytes: int
    active: bool


class MailboxSummary(BaseModel):
    username: str
    name: str
    domain: str
    quota_bytes: int
    messages: int
    active: bool


class MailResponse(BaseModel):
    providers: list[ProviderSummary]
    domains: list[MailDomainSummary]
    mailboxes: list[MailboxSummary]


class MailDomainCreateRequest(BaseModel):
    domain: str
    description: str = ""
    quota_mb: int = Field(default=10240, ge=1, le=1048576)


class MailDnsRecordReport(BaseModel):
    name: str
    record_type: str
    status: str  # created | failed | skipped
    detail: str = ""


class MailDomainCreateResponse(BaseModel):
    domain: str
    dkim_name: str = ""
    dkim_txt: str = ""
    relay_assigned: bool = False
    dns_zone: str = ""
    dns_records: list[MailDnsRecordReport] = []


class MailboxCreateRequest(BaseModel):
    local_part: str
    domain: str
    name: str = ""
    password: str
    quota_mb: int = 3072


class MailAliasCreateRequest(BaseModel):
    address: str
    goto: str


class MailAliasSummary(BaseModel):
    id: int
    address: str
    goto: str
    domain: str
    active: bool


class MailDkimResponse(BaseModel):
    domain: str
    dkim_name: str = ""
    dkim_txt: str = ""


class MailRelayhostCreateRequest(BaseModel):
    hostname: str
    username: str
    password: str


class MailRelayhostCreateResponse(BaseModel):
    ok: bool = True
    relayhost_id: int = 0


class MailRelayhostSummary(BaseModel):
    id: int
    hostname: str
    username: str
    active: bool = True
    used_by_domains: str = ""


class DNSZoneSummary(BaseModel):
    id: str
    name: str
    status: str
    account_name: str
    paused: bool


class DNSRecordSummary(BaseModel):
    id: str
    type: str
    name: str
    content: str
    ttl: int
    proxied: bool | None = None
    priority: int | None = None


class DNSResponse(BaseModel):
    providers: list[ProviderSummary]
    selected_zone: str
    zones: list[DNSZoneSummary]
    records: list[DNSRecordSummary]


class DNSRecordCreateRequest(BaseModel):
    type: str
    name: str
    content: str
    ttl: int = 1
    proxied: bool = False
    priority: int | None = None


class EnvVarCreateRequest(BaseModel):
    key: str
    value: str
    is_preview: bool = False
    is_build_time: bool = False


class ZoneSettings(BaseModel):
    ssl: str = ""
    always_use_https: str = ""
    development_mode: str = ""
    security_level: str = ""
    dnssec: str = ""


class ZoneSettingUpdateRequest(BaseModel):
    setting: str
    value: str


class DnssecUpdateRequest(BaseModel):
    status: str


class CachePurgeRequest(BaseModel):
    everything: bool = True
    files: list[str] = []


class ZoneAnalyticsPoint(BaseModel):
    date: str
    requests: int = 0
    bytes: int = 0
    cached_requests: int = 0
    threats: int = 0
    uniques: int = 0


class ZoneAnalyticsTotals(BaseModel):
    requests: int = 0
    bytes: int = 0
    cached_requests: int = 0
    threats: int = 0
    uniques: int = 0


class ZoneAnalytics(BaseModel):
    zone_id: str
    since: str = ""
    until: str = ""
    points: list[ZoneAnalyticsPoint] = []
    totals: ZoneAnalyticsTotals = ZoneAnalyticsTotals()


class DnsExportResponse(BaseModel):
    zone_id: str
    bind: str
    record_count: int = 0


class DnsImportRequest(BaseModel):
    bind: str


class AppTemplateSummary(BaseModel):
    slug: str
    name: str
    description: str = ""
    category: str = ""
    tags: list[str] = []
    logo: str = ""
    port: str = ""


class InstalledAppSummary(BaseModel):
    project: str
    name: str
    template: str = ""
    status: str = "unknown"
    domain: str = ""


class AppInstallRequest(BaseModel):
    slug: str
    name: str | None = None
    domain: str | None = None


class AppActionResponse(BaseModel):
    ok: bool = True
    message: str
    project: str = ""
    domain: str = ""


class GitDeployRequest(BaseModel):
    git_url: str
    ref: str = "main"
    name: str
    port: int = 3000


class DeployStartResponse(BaseModel):
    ok: bool = True
    deployment_id: str
    status: str = "queued"


class DeploymentStatus(BaseModel):
    id: str
    project: str
    status: str
    git_url: str = ""
    ref: str = "main"
    builder: str = ""
    image: str = ""
    commit: str = ""
    port: int = 0
    domain: str = ""
    log: str = ""
    error: str = ""
    created_at: str = ""


class AppEnvVarRequest(BaseModel):
    key: str
    value: str
    is_secret: bool = False
    is_build_time: bool = False


class AppEnvVarSummary(BaseModel):
    key: str
    value: str  # masked ("••••••") when is_secret
    is_secret: bool = False
    is_build_time: bool = False


class AppComputeSample(BaseModel):
    name: str
    cpu_percent: float = 0.0
    mem_used_mb: float = 0.0
    mem_limit_mb: float = 0.0
    mem_percent: float = 0.0
    net_rx_mb: float = 0.0
    net_tx_mb: float = 0.0
    pids: int = 0


class AppComputeResponse(BaseModel):
    project: str
    samples: list[AppComputeSample] = []
    cpu_percent: float = 0.0  # summed across the app's containers
    mem_used_mb: float = 0.0


class InfraServerCreateRequest(BaseModel):
    name: str
    server_type: str = ""  # empty = platform default (role-aware)
    image: str = ""
    location: str = ""
    role: str = "docker"  # "docker" (bare Docker bootstrap) | "mail" (dedicated Mailcow host)
    mail_hostname: str = ""  # required when role == "mail" — the MX-target FQDN, e.g. mail.example.com


class InfraServerSummary(BaseModel):
    id: int
    name: str
    status: str = ""
    server_type: str = ""
    ipv4: str = ""
    location: str = ""
    created: str = ""


class InfraServerCreated(BaseModel):
    server: InfraServerSummary
    action_status: str = ""  # success | error | running (bootstrap continues via cloud-init)
    root_password: str = ""  # shown once when no SSH key is attached — never stored


class DomainRequest(BaseModel):
    project: str
    hostname: str


class DomainSummary(BaseModel):
    id: str
    project: str
    hostname: str
    status: str  # pending | verified
    txt_name: str = ""
    txt_value: str = ""
    cname_target: str = ""


class DeployHookRequest(BaseModel):
    project: str
    git_url: str
    ref: str = "main"
    port: int = 3000
    previews: bool = True  # branch pushes get preview environments (Vercel parity)


class DeployHookSummary(BaseModel):
    id: str
    project: str
    git_url: str = ""
    ref: str = "main"
    port: int = 3000
    enabled: bool = True
    previews: bool = True


class BuildDiagnosis(BaseModel):
    """AI/heuristic diagnosis of a deployment's build outcome (``tetra ai explain``)."""

    deployment_id: str
    status: str
    summary: str
    category: str
    likely_causes: list[str] = []
    suggested_fixes: list[str] = []
    confidence: str  # low | medium | high
    source: str  # heuristic | ai


class PreviewSummary(BaseModel):
    """A live per-branch preview environment (its own stack + subdomain)."""

    id: str
    project: str
    branch: str
    preview_project: str
    domain: str = ""
    last_deployment_id: str = ""


class DeployHookCreated(BaseModel):
    id: str
    project: str
    url: str
    secret: str  # shown once — paste into GitHub's webhook secret
    ref: str = "main"


class AdminResponse(BaseModel):
    admins: list[AdminSummary]
    providers: list[ProviderSummary]


class TenantSummary(BaseModel):
    id: str
    name: str
    slug: str
    is_active: bool
    status: str = ""
    plan_key: str = ""


class TenantCreateRequest(BaseModel):
    name: str
    slug: str


class TenantAdminCreateRequest(BaseModel):
    tenant_slug: str
    email: str
    full_name: str
    password: str


class TenantResourceSummary(BaseModel):
    id: str
    tenant_id: str
    tenant_slug: str
    tenant_name: str
    provider: str
    resource_type: str
    external_id: str
    display_name: str


class TenantResourceCreateRequest(BaseModel):
    tenant_slug: str
    provider: str
    resource_type: str
    external_id: str
    display_name: str


class PlanSummary(BaseModel):
    id: str
    key: str
    name: str
    description: str = ""
    price_cents: int
    currency: str
    max_apps: int
    max_domains: int
    cpu_millicores: int
    mem_mb: int
    disk_mb: int
    is_archived: bool
    sort_order: int


class PlanCreateRequest(BaseModel):
    key: str
    name: str
    description: str = ""
    price_cents: int = 0
    currency: str = "usd"
    max_apps: int
    max_domains: int
    cpu_millicores: int
    mem_mb: int
    disk_mb: int
    sort_order: int = 0


class PlanUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    price_cents: int | None = None
    currency: str | None = None
    max_apps: int | None = None
    max_domains: int | None = None
    cpu_millicores: int | None = None
    mem_mb: int | None = None
    disk_mb: int | None = None
    sort_order: int | None = None


class UsageResponse(BaseModel):
    """Per-tenant quota usage vs plan limits.

    Only ``apps`` is enforced (quota_exceeded raised on install).
    cpu/mem/disk/domains are advisory — surfaced for visibility but not blocked.
    """

    plan_key: str = ""
    apps_used: int
    apps_limit: int
    cpu_millicores_used: int
    cpu_millicores_limit: int
    mem_mb_used: int
    mem_mb_limit: int
    disk_mb_used: int
    disk_mb_limit: int
    domains_used: int
    domains_limit: int
    # Dimensions that are actively enforced (block the action when exceeded).
    enforced: list[str] = ["apps"]


class TenantStatusCounts(BaseModel):
    """Tenant counts bucketed by lifecycle status, plus the grand total."""

    active: int = 0
    pending: int = 0
    suspended: int = 0
    rejected: int = 0
    total: int = 0


class PlatformTotals(BaseModel):
    """Cross-tenant headline counts for the platform operator."""

    tenants: int = 0
    admins: int = 0
    apps: int = 0
    databases: int = 0
    plans: int = 0


class PlatformResourceUsage(BaseModel):
    """Sum of committed resource allocations across every tenant resource."""

    cpu_millicores: int = 0
    mem_mb: int = 0
    disk_mb: int = 0


class AuditEventSummary(BaseModel):
    actor_email: str
    action: str
    target: str
    details: str = ""
    created_at: str = ""


class AuditLogResponse(BaseModel):
    """A filtered, paginated page of platform audit events (platform-admin only)."""

    events: list[AuditEventSummary]
    total: int
    limit: int
    offset: int


# ── Reseller (Cloudflare plans + services on tenant zones) ──────────────────
class ResellableServiceSummary(BaseModel):
    key: str
    name: str
    category: str  # plan | security | performance | developer
    activation: str  # plan | toggle | addon
    rate_plan: str = ""
    description: str = ""


class CloudflarePlanSummary(BaseModel):
    id: str = ""
    name: str = ""
    price: float = 0.0
    currency: str = ""
    frequency: str = ""
    can_subscribe: bool = False
    is_subscribed: bool = False


class ZoneSubscriptionSummary(BaseModel):
    id: str = ""
    state: str = ""
    price: float = 0.0
    currency: str = ""
    frequency: str = ""
    rate_plan_id: str = ""


class PlanActivateRequest(BaseModel):
    rate_plan_id: str
    frequency: str = "monthly"


class ServiceActivateResponse(BaseModel):
    service: str
    note: str
    state: str = ""


# ── AI reselling (OpenRouter per-tenant runtime keys) ───────────────────────
class AiModelSummary(BaseModel):
    id: str = ""
    name: str = ""
    context_length: int = 0
    prompt_price: str = ""
    completion_price: str = ""


class AiKeySummary(BaseModel):
    hash: str = ""
    label: str = ""
    name: str = ""
    limit: float | None = None
    usage: float = 0.0
    disabled: bool = False


class AiKeyProvisionRequest(BaseModel):
    label: str
    limit: float | None = None
    limit_reset: str = "monthly"


class AiKeyCreated(BaseModel):
    key: str  # the runtime-key secret — surfaced ONCE, never stored
    hash: str
    label: str
    limit: float | None = None


class AiKeyUpdateRequest(BaseModel):
    limit: float | None = None
    disabled: bool | None = None


class PlatformOverview(BaseModel):
    """Aggregate platform state for the super-admin command center.

    Platform-admin only. Composes counts, committed resource allocation, the
    pending-approval queue, and the most recent audit events into one payload so
    the console renders without fanning out N requests.
    """

    tenant_status: TenantStatusCounts
    totals: PlatformTotals
    committed_resources: PlatformResourceUsage
    pending_tenants: list[TenantSummary] = []
    recent_events: list[AuditEventSummary] = []


class AnalyticsSummary(BaseModel):
    pageviews: int = 0
    visitors: int = 0
    visits: int = 0
    bounce_rate: int = 0
    avg_seconds: int = 0


class AnalyticsSeriesPoint(BaseModel):
    date: str
    pageviews: int = 0
    sessions: int = 0


class AnalyticsMetric(BaseModel):
    label: str
    count: int = 0


class ProjectAnalytics(BaseModel):
    """Per-project web analytics (Umami). ``configured`` reflects whether the
    platform has Umami wired; ``ready`` whether this project has a resolvable
    website. When not configured/ready, the report fields stay empty."""

    configured: bool = False
    ready: bool = False
    period: str = "7d"
    reason: str = ""
    website_id: str = ""
    tracking_snippet: str = ""
    summary: AnalyticsSummary = Field(default_factory=AnalyticsSummary)
    series: list[AnalyticsSeriesPoint] = []
    top_pages: list[AnalyticsMetric] = []
    top_referrers: list[AnalyticsMetric] = []


class ErrorIssue(BaseModel):
    id: str
    title: str
    culprit: str = ""
    level: str = "error"
    count: int = 0
    user_count: int = 0
    last_seen: str = ""
    status: str = "unresolved"
    permalink: str = ""


class ProjectErrors(BaseModel):
    """Per-project error tracking (GlitchTip). ``configured`` reflects whether the
    platform has GlitchTip wired; ``ready`` whether this project's GlitchTip project
    is resolvable. ``dsn`` is the Sentry-SDK endpoint to add to the app."""

    configured: bool = False
    ready: bool = False
    reason: str = ""
    project_slug: str = ""
    dsn: str = ""
    issues: list[ErrorIssue] = []


class DatabaseSummary(BaseModel):
    id: str
    name: str
    type: str = ""
    status: str = "unknown"
    internal_db_url: str = ""
    image: str = ""


class DatabaseProvisionRequest(BaseModel):
    """Request to provision a new managed database via Coolify.

    db_type must be one of the Coolify-supported database types.
    No tenant_id, role, or owner fields — tenant is always the caller's tenant.
    """

    db_type: str = Field(
        ...,
        description="One of: postgresql, mysql, mariadb, mongodb, redis, keydb, dragonfly, clickhouse",
    )
    name: str = Field(..., min_length=1, max_length=120)
    server_uuid: str
    project_uuid: str
    environment_name: str


class BackupConfigSummary(BaseModel):
    id: str
    frequency: str = ""
    retention_days: int = 0
    s3_storage_id: str = ""


class BackupCreateRequest(BaseModel):
    frequency: str = "0 2 * * *"
    retention_days: int = 7
    s3_storage_id: str = ""
