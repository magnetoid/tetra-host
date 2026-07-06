import { Card, CardHeader } from "@/components/ui/card"
import { PageHeader } from "@/components/ui/page-header"
import { TenantRowActions } from "@/components/tenants/tenant-row-actions"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { TenantRecord } from "@/lib/types"

const STATUS_COLORS: Record<string, string> = {
  active: "text-status-ok",
  pending: "text-status-warn",
  suspended: "text-status-warn",
  rejected: "text-status-err",
}

export default async function TenantsPage() {
  const session = await requireConsoleSession()

  if (session.admin.role !== "platform_admin") {
    return (
      <div className="space-y-6">
        <PageHeader
          eyebrow="Platform administration"
          title="Tenants"
          description="Manage tenant organisations on the platform."
        />
        <Card>
          <p className="text-sm text-muted-foreground">
            Tenant management is restricted to platform administrators.
          </p>
        </Card>
      </div>
    )
  }

  const tenants = await fetchBackend<TenantRecord[]>("/tenants", {
    token: session.token,
  })

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Platform administration"
        title="Tenants"
        description="Review, approve, suspend, and manage tenant organisations. Platform-admin only."
      />

      <Card>
        <CardHeader
          title="All tenants"
          action={`${tenants.length} tenant${tenants.length === 1 ? "" : "s"}`}
        />
        <div className="mt-4">
          {tenants.length === 0 ? (
            <p className="text-sm text-muted-foreground">No tenants yet.</p>
          ) : (
            <div className="overflow-hidden rounded-2xl border border-border">
              <table className="min-w-full divide-y divide-border text-sm">
                <thead className="bg-background/60 text-left text-muted-foreground">
                  <tr>
                    <th className="px-4 py-3 font-medium">Name</th>
                    <th className="px-4 py-3 font-medium">Slug</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-4 py-3 font-medium">Plan</th>
                    <th className="px-4 py-3 text-right font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border bg-background">
                  {tenants.map((tenant) => (
                    <tr key={tenant.id}>
                      <td className="px-4 py-3 font-medium">{tenant.name}</td>
                      <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                        {tenant.slug}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`text-xs font-medium capitalize ${
                            STATUS_COLORS[tenant.status ?? "active"] ?? "text-muted-foreground"
                          }`}
                        >
                          {tenant.status ?? "active"}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                        {tenant.plan_key ?? "—"}
                      </td>
                      <td className="px-4 py-3 text-right">
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
    </div>
  )
}
