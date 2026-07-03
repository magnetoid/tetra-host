export type ProviderStatus = "connected" | "degraded" | "not_configured"

export interface HealthResponse {
  ok: boolean
  app: string
  env: "development" | "staging" | "production"
  version: string
  requestId?: string
  request_id?: string
}

export interface ReadinessResponse {
  ok: boolean
  providers: {
    coolify: boolean
    mailcow: boolean
    cloudflare: boolean
  }
  auth: {
    session: boolean
    csrf: boolean
  }
}

export interface ProviderSummary {
  name: string
  status: ProviderStatus
  detail: string
}

export interface DashboardResponse {
  providers: ProviderSummary[]
  metrics: {
    projects: number
    unhealthy_projects: number
    mail_domains: number
    dns_zones: number
    admins: number
  }
}

export interface ProjectRecord {
  id: string
  name: string
  status: string
  primary_domain: string
  repository: string
  environment: string
  updated_at: string
  healthcheck_enabled: boolean
}

export interface MailDomainRecord {
  domain_name: string
  mailboxes: number
  aliases: number
  quota_bytes: number
  active: boolean
}

export interface MailboxRecord {
  username: string
  name: string
  domain: string
  quota_bytes: number
  messages: number
  active: boolean
}

export interface MailResponse {
  providers: ProviderSummary[]
  domains: MailDomainRecord[]
  mailboxes: MailboxRecord[]
}

export interface DNSZoneRecord {
  id: string
  name: string
  status: string
  account_name: string
  paused: boolean
}

export interface DNSRecord {
  id: string
  type: string
  name: string
  content: string
  ttl: number
  proxied: boolean | null
  priority?: number | null
}

export interface DNSResponse {
  providers: ProviderSummary[]
  selected_zone: string
  zones: DNSZoneRecord[]
  records: DNSRecord[]
}

export interface ZoneSettings {
  ssl: string
  always_use_https: string
  development_mode: string
  security_level: string
  dnssec: string
}

export interface ZoneAnalyticsPoint {
  date: string
  requests: number
  bytes: number
  cached_requests: number
  threats: number
  uniques: number
}

export interface ZoneAnalyticsTotals {
  requests: number
  bytes: number
  cached_requests: number
  threats: number
  uniques: number
}

export interface ZoneAnalytics {
  zone_id: string
  since: string
  until: string
  points: ZoneAnalyticsPoint[]
  totals: ZoneAnalyticsTotals
}

export interface AppTemplate {
  slug: string
  name: string
  description: string
  category: string
  tags: string[]
  logo: string
  port: string
}

export interface InstalledApp {
  project: string
  name: string
  template: string
  status: string
  domain: string
}

export interface AdminRecord {
  id: string
  email: string
  full_name: string
  is_active: boolean
  role?: string
  tenant_id?: string
  tenant_slug?: string
  tenant_name?: string
  tenant_status?: string
}

export interface Plan {
  id: string
  key: string
  name: string
  description: string
  price_cents: number
  currency: string
  max_apps: number
  max_domains: number
  cpu_millicores: number
  mem_mb: number
  disk_mb: number
  is_archived: boolean
  sort_order: number
}

export interface AdminResponse {
  admins: AdminRecord[]
  providers: ProviderSummary[]
}

export interface ProjectDeploymentRecord {
  id: string
  status: string
  created_at: string
  updated_at: string
  commit: string
  branch: string
}

export interface DeploymentLogLine {
  output: string
  type: string
  timestamp: string
}

export interface DeploymentDetail {
  id: string
  status: string
  created_at: string
  updated_at: string
  commit: string
  branch: string
  log_lines: DeploymentLogLine[]
}

export interface TenantRecord {
  id: string
  name: string
  slug: string
  is_active: boolean
  status?: string
  plan_key?: string
}

export interface TenantStatusCounts {
  active: number
  pending: number
  suspended: number
  rejected: number
  total: number
}

export interface PlatformTotals {
  tenants: number
  admins: number
  apps: number
  databases: number
  plans: number
}

export interface PlatformResourceUsage {
  cpu_millicores: number
  mem_mb: number
  disk_mb: number
}

export interface AuditEventRecord {
  actor_email: string
  action: string
  target: string
  details: string
  created_at: string
}

export interface PlatformOverview {
  tenant_status: TenantStatusCounts
  totals: PlatformTotals
  committed_resources: PlatformResourceUsage
  pending_tenants: TenantRecord[]
  recent_events: AuditEventRecord[]
}

export interface AnalyticsSummary {
  pageviews: number
  visitors: number
  visits: number
  bounce_rate: number
  avg_seconds: number
}

export interface AnalyticsSeriesPoint {
  date: string
  pageviews: number
  sessions: number
}

export interface AnalyticsMetric {
  label: string
  count: number
}

export interface ProjectAnalytics {
  configured: boolean
  ready: boolean
  period: string
  reason?: string
  website_id?: string
  tracking_snippet?: string
  summary: AnalyticsSummary
  series: AnalyticsSeriesPoint[]
  top_pages: AnalyticsMetric[]
  top_referrers: AnalyticsMetric[]
}

export interface ErrorIssue {
  id: string
  title: string
  culprit: string
  level: string
  count: number
  user_count: number
  last_seen: string
  status: string
  permalink: string
}

export interface ProjectErrors {
  configured: boolean
  ready: boolean
  reason?: string
  project_slug?: string
  dsn?: string
  issues: ErrorIssue[]
}

export interface ProjectActionResponse {
  ok: boolean
  message: string
  deployment_id?: string
}
export interface LoginResponse {
  token: string
  admin: AdminRecord
}

export interface DocEntry {
  slug: string
  title: string
  summary: string
  sections: Array<{
    heading: string
    body: string[]
  }>
}

export interface Usage {
  plan_key: string
  apps_used: number
  apps_limit: number
  cpu_millicores_used: number
  cpu_millicores_limit: number
  mem_mb_used: number
  mem_mb_limit: number
  disk_mb_used: number
  disk_mb_limit: number
  domains_used: number
  domains_limit: number
  enforced: string[]
}

export interface ComputeSample {
  name: string
  cpu_percent: number
  mem_used_mb: number
  mem_limit_mb: number
  mem_percent: number
  net_rx_mb: number
  net_tx_mb: number
  pids: number
}

export interface ComputeMetrics {
  project: string
  samples: ComputeSample[]
  cpu_percent: number
  mem_used_mb: number
}

export interface DomainRecord {
  id: string
  project: string
  hostname: string
  status: "pending" | "verified" | string
  txt_name: string
  txt_value: string
  cname_target: string
}

export interface DeploymentRecord {
  id: string
  project: string
  status: "queued" | "building" | "ready" | "error" | string
  git_url: string
  ref: string
  builder: string
  image: string
  commit: string
  port: number
  domain: string
  log: string
  error: string
  created_at: string
}

export interface AppEnvVar {
  key: string
  value: string // masked ("••••••") when is_secret
  is_secret: boolean
  is_build_time: boolean
}

export interface BuildDiagnosis {
  deployment_id: string
  status: string
  summary: string
  category: string
  likely_causes: string[]
  suggested_fixes: string[]
  confidence: "low" | "medium" | "high" | string
  source: "heuristic" | "ai" | string
}

export interface DeployHook {
  id: string
  project: string
  git_url: string
  ref: string
  port: number
  enabled: boolean
  previews: boolean
}

export interface PreviewRecord {
  id: string
  project: string
  branch: string
  preview_project: string
  domain: string
  last_deployment_id: string
}

export interface DeployHookCreated {
  id: string
  project: string
  url: string
  secret: string // shown once
  ref: string
}
