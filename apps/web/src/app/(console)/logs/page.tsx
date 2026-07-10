import { LogsViewer } from "@/components/logs/logs-viewer"
import { PageHeader } from "@/components/ui/page-header"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { InstalledApp } from "@/lib/types"

export default async function LogsPage() {
  const session = await requireConsoleSession()

  const apps = await fetchBackend<InstalledApp[]>("/apps", { token: session.token }).catch(
    () => [] as InstalledApp[],
  )

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Observability"
        title="Logs"
        description="Runtime logs for any of your apps — pick one, refresh, and filter the stream."
      />
      <LogsViewer apps={apps} />
    </div>
  )
}
