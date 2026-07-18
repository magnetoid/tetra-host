import { AdminTenantsTable } from "@/components/admin/admin-tenants-table"
import { AdminsTable } from "@/components/admin/admins-table"
import { DegradedBanner } from "@/components/ui/degraded-banner"
import { PageHeader } from "@/components/ui/page-header"
import { ProviderCard } from "@/components/ui/provider-card"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import { degradedSources, fetchDegraded } from "@/lib/fetch-degraded"
import type { AdminResponse, TenantRecord } from "@/lib/types"

export default async function AdminPage() {
  const session = await requireConsoleSession()
  const [adminData, tenantsRes] = await Promise.all([
    fetchBackend<AdminResponse>("/admin", { token: session.token }),
    fetchDegraded<TenantRecord[]>("/tenants", "Tenants", [], { token: session.token }),
  ])
  const tenants = tenantsRes.data

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Platform administration"
        title="Admin"
        description="Review tenant administrators and provider readiness for the control plane."
      />

      <DegradedBanner sources={degradedSources([tenantsRes])} />

      <section className="grid gap-4 lg:grid-cols-[1fr_1fr]">
        <AdminTenantsTable tenants={tenants} />

        <div className="rounded-lg border border-border bg-muted p-6">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Provider readiness</h2>
            <span className="text-sm text-muted-foreground">Current environment</span>
          </div>
          <div className="mt-4 space-y-3">
            {adminData.providers.map((provider) => (
              <ProviderCard key={provider.name} provider={provider} />
            ))}
          </div>
        </div>
      </section>

      <AdminsTable admins={adminData.admins} />
    </div>
  )
}
