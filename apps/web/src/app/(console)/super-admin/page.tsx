import Link from "next/link"

import { TenantRowActions } from "@/components/tenants/tenant-row-actions"
import { Card, CardHeader } from "@/components/ui/card"
import { EmptyState } from "@/components/ui/empty-state"
import { MetricCard } from "@/components/ui/metric-card"
import { PageHeader } from "@/components/ui/page-header"
import { StatCard } from "@/components/ui/stat-card"
import { StatusBadge } from "@/components/ui/status-badge"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import { faBox, faDatabase, faLayerGroup, faUsers, faUserShield } from "@/lib/icons"
import type { PlatformOverview } from "@/lib/types"

function vcpus(millicores: number): string {
  return (millicores / 1000).toFixed(millicores % 1000 === 0 ? 0 : 1)
}

function gib(mb: number): string {
  return (mb / 1024).toFixed(mb % 1024 === 0 ? 0 : 1)
}

function formatWhen(iso: string): string {
  if (!iso) return ""
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString()
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

  const overview = await fetchBackend<PlatformOverview>("/admin/overview", {
    token: session.token,
  })
  const { tenant_status, totals, committed_resources, pending_tenants, recent_events } = overview

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Platform operations"
        title="Super Admin"
        description="Cross-tenant command center: platform totals, the approval queue, and recent activity. Platform-admin only."
      />

      {/* Headline totals */}
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <StatCard icon={faUsers} label="Tenants" value={totals.tenants} accent="text-status-live" />
        <StatCard icon={faUserShield} label="Admins" value={totals.admins} accent="text-primary" />
        <StatCard icon={faBox} label="Apps" value={totals.apps} accent="text-status-ok" />
        <StatCard icon={faDatabase} label="Databases" value={totals.databases} accent="text-status-warn" />
        <StatCard icon={faLayerGroup} label="Plans" value={totals.plans} accent="text-status-err" />
      </section>

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
      <Card>
        <CardHeader title="Pending approval" action={`${pending_tenants.length} waiting`} />
        <div className="mt-4">
          {pending_tenants.length === 0 ? (
            <EmptyState
              title="No tenants awaiting approval"
              description="New signups in the pending state appear here for review."
            />
          ) : (
            <div className="overflow-hidden rounded-2xl border border-border">
              <table className="min-w-full divide-y divide-border text-sm">
                <thead className="bg-background/60 text-left text-muted-foreground">
                  <tr>
                    <th className="px-4 py-3 font-medium">Name</th>
                    <th className="px-4 py-3 font-medium">Slug</th>
                    <th className="px-4 py-3 font-medium">Plan</th>
                    <th className="px-4 py-3 text-right font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border bg-background">
                  {pending_tenants.map((tenant) => (
                    <tr key={tenant.id}>
                      <td className="px-4 py-3 font-medium">{tenant.name}</td>
                      <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{tenant.slug}</td>
                      <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{tenant.plan_key || "—"}</td>
                      <td className="px-4 py-3">
                        <TenantRowActions tenant={tenant} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </Card>

      {/* Recent activity */}
      <Card>
        <CardHeader title="Recent activity" action={`${recent_events.length} events`} />
        <div className="mt-4">
          {recent_events.length === 0 ? (
            <EmptyState
              title="No activity yet"
              description="Audited platform actions — approvals, suspensions, and more — appear here."
            />
          ) : (
            <div className="overflow-hidden rounded-2xl border border-border">
              <table className="min-w-full divide-y divide-border text-sm">
                <thead className="bg-background/60 text-left text-muted-foreground">
                  <tr>
                    <th className="px-4 py-3 font-medium">When</th>
                    <th className="px-4 py-3 font-medium">Action</th>
                    <th className="px-4 py-3 font-medium">Actor</th>
                    <th className="px-4 py-3 font-medium">Target</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border bg-background">
                  {recent_events.map((event, i) => (
                    <tr key={`${event.action}-${event.created_at}-${i}`}>
                      <td className="whitespace-nowrap px-4 py-3 font-mono text-xs tabular-nums text-muted-foreground">
                        {formatWhen(event.created_at)}
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge value={event.action} />
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{event.actor_email}</td>
                      <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{event.target}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </Card>
    </div>
  )
}
