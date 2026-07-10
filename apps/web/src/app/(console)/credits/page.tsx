import { AdminCredits } from "@/components/credits/admin-credits"
import { Card } from "@/components/ui/card"
import { PageHeader } from "@/components/ui/page-header"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { TenantCreditOverview } from "@/lib/types"

export default async function CreditsPage() {
  const session = await requireConsoleSession()

  if (session.admin.role !== "platform_admin") {
    return (
      <div className="space-y-6">
        <PageHeader
          eyebrow="Platform billing"
          title="AI credits"
          description="Fund tenants' prepaid AI credit and track their spend."
        />
        <Card>
          <p className="text-sm text-muted-foreground">
            AI credit management is restricted to platform administrators.
          </p>
        </Card>
      </div>
    )
  }

  const rows = await fetchBackend<TenantCreditOverview[]>("/billing/credits/overview", {
    token: session.token,
  }).catch(() => [] as TenantCreditOverview[])

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Platform billing"
        title="AI credits"
        description="Every tenant's prepaid AI credit balance and 30-day metered spend. Top up after payment."
      />
      <AdminCredits rows={rows} />
    </div>
  )
}
