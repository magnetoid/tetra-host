from pydantic import BaseModel, ConfigDict


class AdminSummary(BaseModel):
    id: str
    email: str
    full_name: str
    is_active: bool
    tenant_id: str
    tenant_slug: str
    tenant_name: str


class AuthResponse(BaseModel):
    token: str
    admin: AdminSummary


class ProviderSummary(BaseModel):
    name: str
    status: str
    detail: str


class DashboardMetrics(BaseModel):
    sites: int
    unhealthy_sites: int
    mail_domains: int
    dns_zones: int
    admins: int


class DashboardResponse(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=False)

    providers: list[ProviderSummary]
    metrics: DashboardMetrics


class SiteSummary(BaseModel):
    id: str
    name: str
    status: str
    primary_domain: str
    repository: str
    environment: str
    updated_at: str
    healthcheck_enabled: bool


class SiteActionResponse(BaseModel):
    ok: bool = True
    message: str
    deployment_id: str = ""


class SiteDeploymentSummary(BaseModel):
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


class AdminResponse(BaseModel):
    admins: list[AdminSummary]
    providers: list[ProviderSummary]


class TenantSummary(BaseModel):
    id: str
    name: str
    slug: str
    is_active: bool


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
