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
    # Coolify project grouping (tenant > project > deployment). Empty for native
    # platform deployments, which group on their own.
    project_uuid: str = ""
    project_name: str = ""
    # Editable build/run settings (surfaced on the app Settings tab).
    fqdn: str = ""
    build_pack: str = ""
    install_command: str = ""
    build_command: str = ""
    start_command: str = ""
    base_directory: str = ""
    publish_directory: str = ""
    ports_exposes: str = ""


class ProjectUpdateRequest(BaseModel):
    """Editable app settings — only provided (non-null) fields are sent to Coolify."""

    name: str | None = None
    description: str | None = None
    fqdn: str | None = None
    build_pack: str | None = None
    install_command: str | None = None
    build_command: str | None = None
    start_command: str | None = None
    base_directory: str | None = None
    publish_directory: str | None = None
    ports_exposes: str | None = None


class AppStorageSummary(BaseModel):
    id: str
    name: str = ""
    mount_path: str = ""
    host_path: str = ""


class AppStorageCreateRequest(BaseModel):
    name: str
    mount_path: str
    host_path: str = ""


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
    source: str = "coolify"  # deployment origin — Coolify-backed application


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
    quota_used_bytes: int = 0
    percent_used: int = 0
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


class MailboxEditRequest(BaseModel):
    """Partial mailbox update — only supplied fields change. `password` resets the
    mailbox password when present; omit it to leave the password untouched."""

    quota_mb: int | None = Field(default=None, ge=1, le=1048576)
    name: str | None = None
    active: bool | None = None
    password: str | None = Field(default=None, min_length=8)


class MailAppPasswordSummary(BaseModel):
    id: int
    name: str
    active: bool = True


class MailAppPasswordCreateRequest(BaseModel):
    app_name: str = Field(default="Tetra app password", max_length=100)


class MailAppPasswordCreateResponse(BaseModel):
    """The generated secret is returned ONCE — mailcow stores it hashed and never
    echoes it again."""

    app_name: str
    password: str


class MailQuarantineItem(BaseModel):
    id: int
    subject: str = ""
    sender: str = ""
    rcpt: str = ""
    score: float = 0.0
    created: int = 0


class MailQuarantineActionRequest(BaseModel):
    ids: list[int] = Field(min_length=1)
    action: str = Field(default="release")  # release | learnham | learnspam


class MailQuarantineDeleteRequest(BaseModel):
    ids: list[int] = Field(min_length=1)


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
    source: str = "git"  # deployment origin — "git" | "app" (marketplace) on the Tetra engine
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


class ApiTokenSummary(BaseModel):
    """A personal API token (no secret — the plaintext is shown only at creation)."""

    id: str
    name: str
    scope: str = "full"  # full | read
    prefix: str
    created_at: str
    last_used_at: str = ""
    expires_at: str = ""


class ApiTokenCreated(ApiTokenSummary):
    """Creation response — carries the plaintext ``token`` exactly once."""

    token: str


class CreateApiTokenRequest(BaseModel):
    name: str
    # A read-only token may only perform GET/HEAD requests (least privilege).
    read_only: bool = False
    expires_in_days: int | None = None


class TwoFactorStatus(BaseModel):
    """Whether the current admin has TOTP two-factor auth enabled."""

    enabled: bool
    backup_codes_remaining: int = 0


class TwoFactorSetupResponse(BaseModel):
    """Provisioning material for enrolling an authenticator app (shown during setup)."""

    secret: str
    otpauth_uri: str


class TwoFactorEnableRequest(BaseModel):
    code: str


class TwoFactorEnableResponse(BaseModel):
    """One-time recovery codes, returned exactly once when 2FA is switched on."""

    backup_codes: list[str]


class TwoFactorDisableRequest(BaseModel):
    password: str


class ErrorDiagnosis(BaseModel):
    """AI/heuristic diagnosis of a captured runtime error (``tetra ai explain-error``)."""

    issue_id: str
    title: str
    culprit: str = ""
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


class PlatformRevenue(BaseModel):
    """Reseller revenue rolled up from the charge ledger (all-time + last 30 days)."""

    resale_total_usd: float = 0.0
    margin_total_usd: float = 0.0
    resale_30d_usd: float = 0.0
    charges: int = 0


class PlatformAiSummary(BaseModel):
    """AI gateway money at a glance across all tenants."""

    credit_float_usd: float = 0.0  # sum of all tenants' prepaid balances (liability)
    spend_30d_usd: float = 0.0
    requests_30d: int = 0


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


# ── AI gateway (shared-key metered chat) + prepaid credit wallet ────────────
class AiStatusResponse(BaseModel):
    mode: str  # "gateway" (Model A) | "keys" (Model B) | "disabled"
    configured: bool = False
    platform_credit_usd: float = 0.0  # shared-key remaining balance (gateway mode)
    platform_used_usd: float = 0.0


class AiChatRequest(BaseModel):
    model: str
    messages: list[dict]
    max_tokens: int | None = None
    temperature: float | None = None


class AiChatUsage(BaseModel):
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    billed_usd: float = 0.0
    request_id: str = ""


class AiChatResponse(BaseModel):
    completion: dict
    usage: AiChatUsage
    balance_usd: float = 0.0


class AiUsageEventSummary(BaseModel):
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    billed_usd: float = 0.0
    created_at: str = ""


class AiUsageReport(BaseModel):
    total_billed_usd: float = 0.0
    total_cost_usd: float = 0.0
    total_requests: int = 0
    by_model: list[dict] = []  # [{model, requests, billed_usd}]
    events: list[AiUsageEventSummary] = []


class CreditTransactionSummary(BaseModel):
    kind: str
    amount_usd: float
    reference: str = ""
    created_at: str = ""


class CreditBalanceResponse(BaseModel):
    balance_usd: float = 0.0
    transactions: list[CreditTransactionSummary] = []


class CreditTopupRequest(BaseModel):
    tenant_id: str
    amount_usd: float = Field(gt=0)


class TenantCreditOverview(BaseModel):
    tenant_id: str
    tenant_name: str = ""
    balance_usd: float = 0.0
    spend_30d_usd: float = 0.0
    requests_30d: int = 0


# ── Public platform status page ─────────────────────────────────────────────
class StatusComponent(BaseModel):
    name: str
    status: str = "operational"  # operational | degraded | down
    detail: str = ""


class StatusResponse(BaseModel):
    overall: str = "operational"
    updated_at: str = ""
    components: list[StatusComponent] = []


# ── Reseller billing (pricing rules + charge ledger) ────────────────────────
class PricingRuleSummary(BaseModel):
    offering_key: str
    provider: str = ""
    cost_shape: str = "recurring"
    wholesale_cost_cents: int = 0
    unit: str = ""
    rule: str = "markup_percent"
    rule_value: float = 0.0
    resale_price_cents: int = 0


class PricingRuleRequest(BaseModel):
    provider: str = ""
    cost_shape: str = "recurring"
    wholesale_cost_cents: int = 0
    unit: str = ""
    rule: str = "markup_percent"
    rule_value: float = 0.0


class PriceQuote(BaseModel):
    offering_key: str
    wholesale_cost_cents: int
    resale_price_cents: int
    margin_cents: int
    rule: str
    rule_value: float


class ResellerChargeSummary(BaseModel):
    id: str
    tenant_id: str
    offering_key: str
    provider: str = ""
    wholesale_cost_cents: int
    resale_price_cents: int
    margin_cents: int
    status: str
    created_at: str = ""


class PlatformOverview(BaseModel):
    """Aggregate platform state for the super-admin command center.

    Platform-admin only. Composes counts, committed resource allocation, the
    pending-approval queue, and the most recent audit events into one payload so
    the console renders without fanning out N requests.
    """

    tenant_status: TenantStatusCounts
    totals: PlatformTotals
    committed_resources: PlatformResourceUsage
    revenue: PlatformRevenue = PlatformRevenue()
    ai: PlatformAiSummary = PlatformAiSummary()
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


class DatabaseTargetOption(BaseModel):
    uuid: str
    name: str


class DatabaseTargets(BaseModel):
    """Coolify servers + projects offered as pickers in the provisioning form."""

    servers: list[DatabaseTargetOption] = []
    projects: list[DatabaseTargetOption] = []


# ── Object storage (Cloudflare R2 bucket reselling) ─────────────────────────
class StorageStatusResponse(BaseModel):
    configured: bool = False
    can_issue_credentials: bool = False
    endpoint: str = ""


class BucketSummary(BaseModel):
    name: str
    display_name: str = ""
    endpoint: str = ""


class BucketProvisionRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)


class BucketCreated(BaseModel):
    name: str
    endpoint: str = ""
    access_key_id: str = ""
    secret_access_key: str = ""  # S3 secret — surfaced ONCE, never stored
    credentials_issued: bool = False


# ── Scheduled jobs (cron-triggered HTTP) ────────────────────────────────────
class ScheduledJobSummary(BaseModel):
    id: str
    name: str = ""
    cron: str = ""
    url: str = ""
    method: str = "GET"
    enabled: bool = True
    last_run_at: str = ""
    last_status: str = ""
    last_detail: str = ""


class JobRunSummary(BaseModel):
    status: str = "ok"
    detail: str = ""
    duration_ms: int = 0
    started_at: str = ""


class JobCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    cron: str = Field(..., min_length=1)
    url: str = Field(..., min_length=1)
    method: str = "GET"


class JobUpdateRequest(BaseModel):
    cron: str | None = None
    url: str | None = None
    method: str | None = None
    enabled: bool | None = None


# ── Team / RBAC ──────────────────────────────────────────────────────────────
class TeamMemberSummary(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    last_login_at: str = ""
    created_at: str = ""


class TeamInviteSummary(BaseModel):
    id: str
    email: str
    role: str
    status: str
    created_at: str = ""
    expires_at: str = ""


class TeamResponse(BaseModel):
    members: list[TeamMemberSummary]
    invites: list[TeamInviteSummary]


class InviteCreateRequest(BaseModel):
    email: str = Field(..., max_length=254)
    role: str = "member"


class InviteCreateResponse(BaseModel):
    invite: TeamInviteSummary
    # Raw token + ready-to-share URL — returned exactly once, never re-fetchable.
    token: str
    accept_url: str


class InvitePreviewResponse(BaseModel):
    tenant_name: str
    email: str
    role: str


class AcceptInviteRequest(BaseModel):
    token: str = Field(..., min_length=1)
    full_name: str = Field(..., min_length=1, max_length=120)
    password: str = Field(..., max_length=200)


class RoleChangeRequest(BaseModel):
    role: str


# ── Single sign-on (OIDC) ────────────────────────────────────────────────────
class SSOConfigResponse(BaseModel):
    configured: bool
    enabled: bool
    provider_label: str = "OpenID Connect"
    issuer: str = ""
    client_id: str = ""
    # Secret is never returned; this flag tells the UI whether one is stored.
    has_secret: bool = False
    allowed_domains: str = ""
    default_role: str = "member"


class SSOConfigRequest(BaseModel):
    issuer: str = Field("", max_length=500)
    client_id: str = Field("", max_length=255)
    # Blank on update = keep the existing stored secret.
    client_secret: str = Field("", max_length=1000)
    allowed_domains: str = Field("", max_length=500)
    default_role: str = "member"
    provider_label: str = Field("OpenID Connect", max_length=80)
    enabled: bool = False


class SSOAuthorizeResponse(BaseModel):
    authorize_url: str


class SSOCallbackRequest(BaseModel):
    code: str = Field(..., min_length=1)
    state: str = Field(..., min_length=1)
    redirect_uri: str = Field(..., min_length=1, max_length=500)
