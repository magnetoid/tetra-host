import { MonitorsManager } from "@/components/monitors/monitors-manager"
import { DegradedBanner } from "@/components/ui/degraded-banner"
import { PageHeader } from "@/components/ui/page-header"
import { requireConsoleSession } from "@/lib/auth"
import { degradedSources, fetchDegraded } from "@/lib/fetch-degraded"
import type { UptimeMonitorSummary } from "@/lib/types"

export const metadata = { title: "Uptime" }

export default async function MonitorsPage() {
  const { token } = await requireConsoleSession()
  const monitorsRes = await fetchDegraded<UptimeMonitorSummary[]>(
    "/account/monitors",
    "Uptime monitors",
    [],
    { token },
  )

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Observability"
        title="Uptime"
        description="HTTP monitors probed every minute. When one goes down or recovers, your notification channels are alerted (app.down / app.up)."
      />
      <DegradedBanner sources={degradedSources([monitorsRes])} />
      <MonitorsManager monitors={monitorsRes.data} />
    </div>
  )
}
