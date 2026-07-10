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
  source?: string // "coolify"
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

export interface PlatformRevenue {
  resale_total_usd: number
  margin_total_usd: number
  resale_30d_usd: number
  charges: number
}

export interface PlatformAiSummary {
  credit_float_usd: number
  spend_30d_usd: number
  requests_30d: number
}

export interface PlatformOverview {
  tenant_status: TenantStatusCounts
  totals: PlatformTotals
  committed_resources: PlatformResourceUsage
  revenue: PlatformRevenue
  ai: PlatformAiSummary
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
  source?: string // "git" | "app" — Tetra-engine origin (derived from builder when absent)
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

// ── Reseller marketplace ────────────────────────────────────────────────────
export interface ResellableService {
  key: string
  name: string
  category: string
  activation: string
  rate_plan: string
  description: string
}

export interface CloudflarePlan {
  id: string
  name: string
  price: number
  currency: string
  frequency: string
  can_subscribe: boolean
  is_subscribed: boolean
}

export interface ZoneSubscription {
  id: string
  state: string
  price: number
  currency: string
  frequency: string
  rate_plan_id: string
}

export interface AiModel {
  id: string
  name: string
  context_length: number
  prompt_price: string
  completion_price: string
}

export interface AiKey {
  hash: string
  label: string
  name: string
  limit: number | null
  usage: number
  disabled: boolean
}

export interface AiKeyCreated {
  key: string // shown once
  hash: string
  label: string
  limit: number | null
}

export interface CreditTransactionRecord {
  kind: string
  amount_usd: number
  reference: string
  created_at: string
}

export interface CreditBalance {
  balance_usd: number
  transactions: CreditTransactionRecord[]
}

export interface AiUsageByModel {
  model: string
  requests: number
  billed_usd: number
}

export interface AiUsageEventRecord {
  model: string
  prompt_tokens: number
  completion_tokens: number
  cost_usd: number
  billed_usd: number
  created_at: string
}

export interface AiUsageReport {
  total_billed_usd: number
  total_cost_usd: number
  total_requests: number
  by_model: AiUsageByModel[]
  events: AiUsageEventRecord[]
}

export interface DatabaseRecord {
  id: string
  name: string
  type: string
  status: string
  internal_db_url: string
  image: string
}

export interface BackupConfig {
  id: string
  frequency: string
  retention_days: number
  s3_storage_id: string
}

export interface DatabaseTargetOption {
  uuid: string
  name: string
}

export interface DatabaseTargets {
  servers: DatabaseTargetOption[]
  projects: DatabaseTargetOption[]
}

export interface BucketRecord {
  name: string
  display_name: string
  endpoint: string
}

export interface BucketCreated {
  name: string
  endpoint: string
  access_key_id: string
  secret_access_key: string
  credentials_issued: boolean
}

export interface StorageStatus {
  configured: boolean
  can_issue_credentials: boolean
  endpoint: string
}

export interface TenantCreditOverview {
  tenant_id: string
  tenant_name: string
  balance_usd: number
  spend_30d_usd: number
  requests_30d: number
}

export interface AiModel {
  id: string
  name: string
  context_length: number
  prompt_price: string
  completion_price: string
}

export interface AiStatus {
  mode: string
  configured: boolean
  platform_credit_usd: number
  platform_used_usd: number
}

export interface StatusComponent {
  name: string
  status: string
  detail: string
}

export interface StatusResponse {
  overall: string
  updated_at: string
  components: StatusComponent[]
}
