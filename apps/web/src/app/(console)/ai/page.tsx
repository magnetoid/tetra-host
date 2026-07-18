import { AiPlayground } from "@/components/ai/ai-playground"
import { DegradedBanner } from "@/components/ui/degraded-banner"
import { PageHeader } from "@/components/ui/page-header"
import { requireConsoleSession } from "@/lib/auth"
import { degradedSources, fetchDegraded } from "@/lib/fetch-degraded"
import type { AiModel, AiStatus, CreditBalance } from "@/lib/types"

const OFFLINE: AiStatus = { mode: "disabled", configured: false, platform_credit_usd: 0, platform_used_usd: 0 }

export default async function AiPage() {
  const session = await requireConsoleSession()

  const [modelsRes, statusRes, creditRes] = await Promise.all([
    fetchDegraded<AiModel[]>("/ai/models", "AI models", [], { token: session.token }),
    fetchDegraded<AiStatus>("/ai/status", "AI status", OFFLINE, { token: session.token }),
    fetchDegraded<CreditBalance>(
      "/billing/credits",
      "Credits",
      { balance_usd: 0, transactions: [] },
      { token: session.token },
    ),
  ])
  const models = modelsRes.data
  const status = statusRes.data
  const credit = creditRes.data

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="AI"
        title="Playground"
        description="Run metered completions through the AI gateway. Each call is billed to your prepaid credit."
      />
      <DegradedBanner sources={degradedSources([modelsRes, statusRes, creditRes])} />
      <AiPlayground models={models} status={status} initialBalanceUsd={credit.balance_usd} />
    </div>
  )
}
