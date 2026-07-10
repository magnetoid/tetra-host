import { SpendOverview } from "@/components/usage/spend-overview"
import { UsageMeters } from "@/components/usage/usage-meters"
import { PageHeader } from "@/components/ui/page-header"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { AiUsageReport, CreditBalance, Usage } from "@/lib/types"

const EMPTY_CREDIT: CreditBalance = { balance_usd: 0, transactions: [] }
const EMPTY_AI: AiUsageReport = {
  total_billed_usd: 0,
  total_cost_usd: 0,
  total_requests: 0,
  by_model: [],
  events: [],
}

export default async function UsagePage() {
  const session = await requireConsoleSession()

  const [usage, credit, ai] = await Promise.all([
    fetchBackend<Usage>("/usage", { token: session.token }),
    fetchBackend<CreditBalance>("/billing/credits", { token: session.token }).catch(
      () => EMPTY_CREDIT,
    ),
    fetchBackend<AiUsageReport>("/ai/usage", { token: session.token }).catch(() => EMPTY_AI),
  ])

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Your plan"
        title="Usage & spend"
        description="Prepaid AI credit, metered AI spend, and quota consumption against your plan limits."
      />

      <section className="space-y-4">
        <h2 className="font-display text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          AI credit & spend
        </h2>
        <SpendOverview credit={credit} ai={ai} />
      </section>

      <section className="space-y-4">
        <h2 className="font-display text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Quota
        </h2>
        <UsageMeters usage={usage} />
      </section>
    </div>
  )
}
