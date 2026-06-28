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
    sites: number
    unhealthy_sites: number
    mail_domains: number
    dns_zones: number
    admins: number
  }
}

export interface SiteRecord {
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
}

export interface DNSResponse {
  providers: ProviderSummary[]
  selected_zone: string
  zones: DNSZoneRecord[]
  records: DNSRecord[]
}

export interface AdminRecord {
  id: string
  email: string
  full_name: string
  is_active: boolean
  tenant_id?: string
  tenant_slug?: string
  tenant_name?: string
}

export interface AdminResponse {
  admins: AdminRecord[]
  providers: ProviderSummary[]
}

export interface SiteDeploymentRecord {
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
}

export interface SiteActionResponse {
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
