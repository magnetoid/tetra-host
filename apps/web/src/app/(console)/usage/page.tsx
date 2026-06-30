import { UsageMeters } from "@/components/usage/usage-meters"
import { PageHeader } from "@/components/ui/page-header"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { Usage } from "@/lib/types"

export default async function UsagePage() {
  const session = await requireConsoleSession()

  const usage = await fetchBackend<Usage>("/usage", {
    token: session.token,
  })

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Your plan"
        title="Usage"
        description="Quota consumption for your tenant against plan limits. Only apps is currently enforced; resource meters are advisory."
      />
      <UsageMeters usage={usage} />
    </div>
  )
}
