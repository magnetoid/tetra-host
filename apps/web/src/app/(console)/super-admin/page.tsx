import Link from "next/link"

import { AdminLinks } from "@/components/admin/admin-links"
import { AuditEventsTable } from "@/components/audit/audit-events-table"
import { PlatformInfra } from "@/components/dashboard/platform-infra"
import { PendingTenantsTable } from "@/components/tenants/pending-tenants-table"
import { Card, CardHeader } from "@/components/ui/card"
import { MetricCard } from "@/components/ui/metric-card"
import { PageHeader } from "@/components/ui/page-header"
import { StatCard } from "@/components/ui/stat-card"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import { fetchDegraded } from "@/lib/fetch-degraded"
import {
  faBox,
  faChartBar,
  faChartLine,
  faDatabase,
  faKey,
  faLayerGroup,
  faUsers,
  faUserShield,
  faWandSparkles,
} from "@/lib/icons"
import type {
  DashboardResponse,
  DNSResponse,
  PlatformOverview,
  StatusResponse,
  ZoneAnalytics,
} from "@/lib/types"

function usd(v: number): string {
  const abs = Math.abs(v)
  return `$${v.toFixed(abs > 0 && abs < 1 ? 4 : 2)}`
}

const DOT: Record<string, string> = {
  operational: "bg-status-ok",
  degraded: "bg-status-warn",
  down: "bg-status-err",
}

function vcpus(millicores: number): string {
  return (millicores / 1000).toFixed(millicores % 1000 === 0 ? 0 : 1)
}

function gib(mb: number): string {
  return (mb / 1024).toFixed(mb % 1024 === 0 ? 0 : 1)
}

export default async function SuperAdminPage() {
  const session = await requireConsoleSession()

  if (session.admin.role !== "platform_admin") {
    return (
      <div className="space-y-6">
        <PageHeader
          eyebrow="Platform operations"
          title="Super Admin"
          description="The platform operator command center."
        />
        <Card>
          <p className="text-sm text-muted-foreground">
            The super-admin command center is restricted to platform administrators.
          </p>
        </Card>
      </div>
    )
  }

  const [overview, status, dashboardRes, dnsRes] = await Promise.all([
    fetchBackend<PlatformOverview>("/admin/overview", { token: session.token }),
    fetchBackend<StatusResponse>("/status", { token: session.token }).catch(() => null),
    fetchDegraded<DashboardResponse>(
      "/dashboard",
      "Providers",
      {
        providers: [],
        metrics: {
          projects: 0, unhealthy_projects: 0, mail_domains: 0, dns_zones: 0, admins: 0,
          mailboxes: 0, deploys_24h: 0, deploys_ok_24h: 0, monitors_total: 0, monitors_up: 0,
        },
        recent_deployments: [],
      },
      { token: session.token },
    ),
    fetchDegraded<DNSResponse>(
      "/dns",
      "DNS",
      { providers: [], selected_zone: "", zones: [], records: [] },
      { token: session.token },
    ),
  ])
  const { tenant_status, totals, committed_resources, revenue, ai, pending_tenants, recent_events } =
    overview

  // Operator infrastructure view ("Tetra AI Cloud" provider health + traffic),
  // relocated here from the tenant Overview.
  const dashboard = dashboardRes.data
  const dns = dnsRes.data
  const primaryZone = dns.selected_zone || dns.zones[0]?.id || ""
  const analyticsRes = primaryZone
    ? await fetchDegraded<ZoneAnalytics | null>(
        `/dns/zones/${primaryZone}/analytics`,
        "Traffic analytics",
        null,
        { token: session.token, searchParams: { days: "7" } },
      )
    : null
  const analytics = analyticsRes?.data ?? null
  const primaryZoneName = dns.zones.find((zone) => zone.id === primaryZone)?.name ?? primaryZone

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Platform operations"
        title="Super Admin"
        description="The operator hub: every platform-admin surface, cross-tenant totals, the approval queue, and recent activity. Platform-admin only."
      />

      {/* Platform administration — the menu for every operator surface. */}
      <AdminLinks />

      {/* Headline totals */}
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <StatCard icon={faUsers} label="Tenants" value={totals.tenants} accent="text-status-live" />
        <StatCard icon={faUserShield} label="Admins" value={totals.admins} accent="text-primary" />
        <StatCard icon={faBox} label="Apps" value={totals.apps} accent="text-status-ok" />
        <StatCard icon={faDatabase} label="Databases" value={totals.databases} accent="text-status-warn" />
        <StatCard icon={faLayerGroup} label="Plans" value={totals.plans} accent="text-status-err" />
      </section>

      {/* Revenue & AI money */}
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        <StatCard icon={faChartBar} label="Resale (all-time)" value={usd(revenue.resale_total_usd)} accent="text-status-ok" />
        <StatCard icon={faChartLine} label="Margin (all-time)" value={usd(revenue.margin_total_usd)} hint={`${revenue.charges} charges`} accent="text-primary" />
        <StatCard icon={faChartBar} label="Resale (30d)" value={usd(revenue.resale_30d_usd)} accent="text-status-live" />
        <StatCard icon={faKey} label="AI credit float" value={usd(ai.credit_float_usd)} hint="tenant prepaid liability" accent="text-status-warn" />
        <StatCard icon={faWandSparkles} label="AI spend (30d)" value={usd(ai.spend_30d_usd)} accent="text-primary" />
        <StatCard icon={faWandSparkles} label="AI calls (30d)" value={ai.requests_30d} accent="text-muted-foreground" />
      </section>

      {/* Platform infrastructure — provider health, traffic, resource mix. */}
      {dashboard.providers.length > 0 ? (
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">Platform infrastructure</h2>
          <PlatformInfra
            providers={dashboard.providers}
            metrics={dashboard.metrics}
            analytics={analytics}
            primaryZoneName={primaryZoneName}
          />
        </div>
      ) : null}

      {/* Platform health */}
      <Card>
        <CardHeader
          title="Platform health"
          action={
            <Link href="/status" className="transition-colors hover:text-foreground">
              Status page →
            </Link>
          }
        />
        <div className="mt-4">
          {status ? (
            <div className="divide-y divide-border">
              {status.components.map((c) => (
                <div key={c.name} className="flex items-center justify-between gap-3 py-2.5">
                  <div className="min-w-0">
                    <div className="text-sm font-medium">{c.name}</div>
                    {c.detail ? <div className="truncate text-xs text-muted-foreground">{c.detail}</div> : null}
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <span className={`size-2 rounded-full ${DOT[c.status] ?? "bg-muted-foreground"}`} />
                    <span className="text-sm capitalize text-muted-foreground">{c.status}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">Health feed unavailable.</p>
          )}
        </div>
      </Card>

      {/* Tenant status breakdown */}
      <Card>
        <CardHeader
          title="Tenant status"
          action={
            <Link href="/tenants" className="transition-colors hover:text-foreground">
              Manage tenants →
            </Link>
          }
        />
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard label="Active" value={tenant_status.active} />
          <MetricCard label="Pending" value={tenant_status.pending} hint="Awaiting approval" />
          <MetricCard label="Suspended" value={tenant_status.suspended} />
          <MetricCard label="Rejected" value={tenant_status.rejected} />
        </div>
      </Card>

      {/* Committed resources */}
      <Card>
        <CardHeader title="Committed resources" action="Summed across all tenant resources" />
        <div className="mt-4 grid gap-4 sm:grid-cols-3">
          <MetricCard
            label="vCPU"
            value={vcpus(committed_resources.cpu_millicores)}
            hint={`${committed_resources.cpu_millicores} millicores`}
          />
          <MetricCard
            label="Memory"
            value={`${gib(committed_resources.mem_mb)} GB`}
            hint={`${committed_resources.mem_mb} MB`}
          />
          <MetricCard
            label="Disk"
            value={`${gib(committed_resources.disk_mb)} GB`}
            hint={`${committed_resources.disk_mb} MB`}
          />
        </div>
      </Card>

      {/* Pending approval queue */}
      <PendingTenantsTable tenants={pending_tenants} />

      {/* Recent activity */}
      <AuditEventsTable
        events={recent_events}
        title="Recent activity"
        action={
          <Link
            href="/audit"
            className="text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            Full audit log →
          </Link>
        }
        emptyMessage="No activity yet. Audited platform actions — approvals, suspensions, and more — appear here."
      />
    </div>
  )
}
