import { AiPlayground } from "@/components/ai/ai-playground"
import { PageHeader } from "@/components/ui/page-header"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { AiModel, AiStatus, CreditBalance } from "@/lib/types"

const OFFLINE: AiStatus = { mode: "disabled", configured: false, platform_credit_usd: 0, platform_used_usd: 0 }

export default async function AiPage() {
  const session = await requireConsoleSession()

  const [models, status, credit] = await Promise.all([
    fetchBackend<AiModel[]>("/ai/models", { token: session.token }).catch(() => [] as AiModel[]),
    fetchBackend<AiStatus>("/ai/status", { token: session.token }).catch(() => OFFLINE),
    fetchBackend<CreditBalance>("/billing/credits", { token: session.token }).catch(
      () => ({ balance_usd: 0, transactions: [] }),
    ),
  ])

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="AI"
        title="Playground"
        description="Run metered completions through the AI gateway. Each call is billed to your prepaid credit."
      />
      <AiPlayground models={models} status={status} initialBalanceUsd={credit.balance_usd} />
    </div>
  )
}
