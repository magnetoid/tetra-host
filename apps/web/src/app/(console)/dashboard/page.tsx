import Link from "next/link"

import { DeploymentsPanel } from "@/components/dashboard/deployments-panel"
import { KpiRail, type Kpi } from "@/components/dashboard/kpi-rail"
import { DegradedBanner } from "@/components/ui/degraded-banner"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import { degradedSources, fetchDegraded } from "@/lib/fetch-degraded"
import { cn } from "@/lib/utils"
import type {
  DashboardResponse,
  DNSResponse,
  InstalledApp,
  MailResponse,
  ProviderSummary,
} from "@/lib/types"

const PROVIDER_TONE: Record<string, string> = {
  ok: "bg-status-ok",
  operational: "bg-status-ok",
  connected: "bg-status-ok",
  degraded: "bg-status-warn",
  error: "bg-status-err",
  not_configured: "bg-muted-foreground",
}

const HEALTHY = new Set(["running", "healthy", "active", "ready"])

function isUnhealthy(app: InstalledApp): boolean {
  return Boolean(app.status) && !HEALTHY.has(app.status.toLowerCase())
}

function pct(n: number, d: number): string {
  if (d <= 0) return "—"
  return `${Math.round((n / d) * 100)}%`
}

function providerDot(status: string): string {
  return PROVIDER_TONE[status] ?? "bg-muted-foreground"
}

function providerWarn(status: string): boolean {
  const dot = providerDot(status)
  return dot === "bg-status-warn" || dot === "bg-status-err"
}

/** Console Overview — editorial dashboard: KPI rail + deployments + resource rail. */
export default async function DashboardPage() {
  const session = await requireConsoleSession()
  const dashboard = await fetchBackend<DashboardResponse>("/dashboard", { token: session.token })
  const [appsRes, mailRes, dnsRes] = await Promise.all([
    fetchDegraded<InstalledApp[]>("/apps", "Apps", [], { token: session.token }),
    fetchDegraded<MailResponse>(
      "/mail",
      "Mail",
      { providers: [], domains: [], mailboxes: [] },
      { token: session.token },
    ),
    fetchDegraded<DNSResponse>(
      "/dns",
      "DNS",
      { providers: [], selected_zone: "", zones: [], records: [] },
      { token: session.token },
    ),
  ])
  const apps = [...appsRes.data].sort((a, b) => (a.name || a.project).localeCompare(b.name || b.project))
  const mail = mailRes.data
  const dns = dnsRes.data
  const degraded = degradedSources([appsRes, mailRes, dnsRes])
  const m = dashboard.metrics

  const kpis: Kpi[] = [
    { label: "Apps", value: String(apps.length || m.projects), sub: `${m.unhealthy_projects} unhealthy`, tone: m.unhealthy_projects > 0 ? "warn" : "muted" },
    { label: "Deploys / 24h", value: String(m.deploys_24h), sub: m.deploys_24h > 0 ? `${pct(m.deploys_ok_24h, m.deploys_24h)} success` : "none yet", tone: "ok" },
    { label: "Uptime", value: pct(m.monitors_up, m.monitors_total), sub: m.monitors_total > 0 ? `${m.monitors_up}/${m.monitors_total} up` : "no monitors", tone: m.monitors_total > 0 && m.monitors_up < m.monitors_total ? "err" : "ok" },
    { label: "DNS zones", value: String(m.dns_zones), sub: "Cloudflare", tone: "muted" },
    { label: "Mailboxes", value: String(m.mailboxes), sub: `${m.mail_domains} domains`, tone: "muted" },
    { label: "Admins", value: String(m.admins), sub: session.admin.tenant_name ?? "Workspace", tone: "muted" },
  ]

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
            {session.admin.tenant_name ?? "Workspace"}
          </div>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">Overview</h1>
        </div>
        <Link
          href="/dashboard"
          className="rounded-md border border-border px-3 py-1.5 text-sm transition-colors hover:bg-accent"
        >
          Refresh
        </Link>
      </div>

      <DegradedBanner sources={degraded} />

      <KpiRail items={kpis} />

      <div className="grid gap-8 lg:grid-cols-[1.6fr_1fr]">
        {/* Left — deployments + apps */}
        <div className="space-y-8">
          <DeploymentsPanel deployments={dashboard.recent_deployments} />

          <section>
            <div className="mb-1 flex items-center justify-between">
              <h2 className="text-sm font-semibold">Apps</h2>
              <Link href="/projects" className="text-sm text-primary transition-colors hover:text-primary/80">
                All projects →
              </Link>
            </div>
            {apps.length === 0 ? (
              <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">
                No apps yet. Create a project, then add a git repo, a template or a database to it.
              </div>
            ) : (
              <div className="divide-y divide-border border-t border-border">
                {apps.slice(0, 8).map((app) => (
                  <Link
                    key={app.project}
                    href={`/apps/${encodeURIComponent(app.project)}/compute`}
                    className="flex items-center gap-4 py-3 text-sm transition-colors hover:bg-accent/50"
                  >
                    <span className={cn("size-1.5 shrink-0 rounded-full", isUnhealthy(app) ? "bg-status-err" : "bg-status-ok")} />
                    <span className="w-40 shrink-0 truncate font-medium">{app.name || app.project}</span>
                    <span className="min-w-0 flex-1 truncate font-mono text-xs text-muted-foreground">
                      {app.domain || "no domain yet"}
                    </span>
                    <span className="shrink-0 text-xs text-muted-foreground">{app.status}</span>
                  </Link>
                ))}
              </div>
            )}
          </section>
        </div>

        {/* Right — resource rail */}
        <aside className="space-y-8 lg:border-l lg:border-border lg:pl-8">
          <RailSection title="Providers">
            <div className="space-y-2.5">
              {dashboard.providers.map((p: ProviderSummary) => (
                <div key={p.name} className="flex items-center justify-between gap-3 text-sm">
                  <span className="flex items-center gap-2">
                    <span className={cn("size-1.5 rounded-full", providerDot(p.status))} />
                    {p.name}
                  </span>
                  <span className={cn("truncate text-xs", providerWarn(p.status) ? "text-status-warn" : "text-muted-foreground")}>
                    {p.detail}
                  </span>
                </div>
              ))}
            </div>
          </RailSection>

          <RailSection title="Uptime" href="/monitors">
            {m.monitors_total > 0 ? (
              <div className="flex items-baseline gap-2">
                <span className="font-mono text-2xl font-semibold tabular-nums">{pct(m.monitors_up, m.monitors_total)}</span>
                <span className="text-xs text-muted-foreground">{m.monitors_up}/{m.monitors_total} monitors up</span>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No uptime monitors yet.</p>
            )}
          </RailSection>

          <RailSection title="Mail" href="/domains">
            {mail.domains.length === 0 ? (
              <p className="text-sm text-muted-foreground">No mail domains yet.</p>
            ) : (
              <div className="space-y-2">
                {mail.domains.slice(0, 4).map((d) => (
                  <div key={d.domain_name} className="flex items-center justify-between text-sm">
                    <span className="truncate font-mono text-xs">{d.domain_name}</span>
                    <span className="shrink-0 text-xs text-muted-foreground">{d.mailboxes} mailboxes</span>
                  </div>
                ))}
              </div>
            )}
          </RailSection>

          <RailSection title="DNS" href="/domains">
            {dns.zones.length === 0 ? (
              <p className="text-sm text-muted-foreground">No DNS zones yet.</p>
            ) : (
              <div className="space-y-2">
                {dns.zones.slice(0, 4).map((z) => (
                  <div key={z.id} className="flex items-center justify-between text-sm">
                    <span className="truncate font-mono text-xs">{z.name}</span>
                    <span className="shrink-0 text-xs text-muted-foreground">{z.status}</span>
                  </div>
                ))}
              </div>
            )}
          </RailSection>
        </aside>
      </div>
    </div>
  )
}

function RailSection({
  title,
  href,
  children,
}: {
  title: string
  href?: string
  children: React.ReactNode
}) {
  return (
    <section>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold">{title}</h2>
        {href ? (
          <Link href={href} className="text-xs text-muted-foreground transition-colors hover:text-foreground">
            View →
          </Link>
        ) : null}
      </div>
      {children}
    </section>
  )
}
