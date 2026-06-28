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
