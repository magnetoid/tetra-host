import { AdminCredits } from "@/components/credits/admin-credits"
import { Card } from "@/components/ui/card"
import { DegradedBanner } from "@/components/ui/degraded-banner"
import { PageHeader } from "@/components/ui/page-header"
import { requireConsoleSession } from "@/lib/auth"
import { degradedSources, fetchDegraded } from "@/lib/fetch-degraded"
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

  const rowsRes = await fetchDegraded<TenantCreditOverview[]>(
    "/billing/credits/overview",
    "Credits",
    [],
    { token: session.token },
  )
  const rows = rowsRes.data

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Platform billing"
        title="AI credits"
        description="Every tenant's prepaid AI credit balance and 30-day metered spend. Top up after payment."
      />
      <DegradedBanner sources={degradedSources([rowsRes])} />
      <AdminCredits rows={rows} />
    </div>
  )
}
