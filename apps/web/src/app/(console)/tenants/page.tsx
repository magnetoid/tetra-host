import { TenantsTable } from "@/components/tenants/tenants-table"
import { Card } from "@/components/ui/card"
import { PageHeader } from "@/components/ui/page-header"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { TenantRecord } from "@/lib/types"

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

      <TenantsTable tenants={tenants} />
    </div>
  )
}
