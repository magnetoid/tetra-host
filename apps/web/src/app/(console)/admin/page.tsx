import { ProviderCard } from "@/components/ui/provider-card"
import { PageHeader } from "@/components/ui/page-header"
import { StatusBadge } from "@/components/ui/status-badge"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { AdminResponse, TenantRecord } from "@/lib/types"

export default async function AdminPage() {
  const session = await requireConsoleSession()
  const [adminData, tenants] = await Promise.all([
    fetchBackend<AdminResponse>("/admin", { token: session.token }),
    fetchBackend<TenantRecord[]>("/tenants", { token: session.token }).catch(() => []),
  ])

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Platform administration"
        title="Admin"
        description="Review tenant administrators and provider readiness for the control plane."
      />

      <section className="grid gap-4 lg:grid-cols-[1fr_1fr]">
        <div className="rounded-2xl border border-border bg-muted p-6">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Tenants</h2>
            <span className="text-sm text-muted-foreground">{tenants.length} records</span>
          </div>
          <div className="mt-4 space-y-3">
            {tenants.map((tenant) => (
              <div key={tenant.id} className="rounded-xl border border-border bg-background p-4">
                <div className="font-medium">{tenant.name}</div>
                <div className="mt-1 font-mono text-xs text-muted-foreground">{tenant.slug}</div>
                <div className="mt-2">
                  <StatusBadge value={tenant.is_active ? "Active" : "Inactive"} />
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-2xl border border-border bg-muted p-6">
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

      <section className="rounded-2xl border border-border bg-muted p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Administrators</h2>
          <span className="text-sm text-muted-foreground">{adminData.admins.length} records</span>
        </div>
        <div className="mt-4 overflow-hidden rounded-2xl border border-border">
          <table className="min-w-full divide-y divide-border text-sm">
            <thead className="bg-background/60 text-left text-muted-foreground">
              <tr>
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Email</th>
                <th className="px-4 py-3 font-medium">Tenant</th>
                <th className="px-4 py-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border bg-background">
              {adminData.admins.map((admin) => (
                <tr key={admin.id}>
                  <td className="px-4 py-3">{admin.full_name}</td>
                  <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{admin.email}</td>
                  <td className="px-4 py-3 text-muted-foreground">{admin.tenant_name ?? admin.tenant_slug}</td>
                  <td className="px-4 py-3">
                    <StatusBadge value={admin.is_active ? "Active" : "Inactive"} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
