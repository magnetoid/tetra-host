import { DatabasesManager } from "@/components/databases/databases-manager"
import { DegradedBanner } from "@/components/ui/degraded-banner"
import { PageHeader } from "@/components/ui/page-header"
import { requireConsoleSession } from "@/lib/auth"
import { degradedSources, fetchDegraded } from "@/lib/fetch-degraded"
import type { DatabaseEngine, DatabaseRecord } from "@/lib/types"

export default async function DatabasesPage() {
  const session = await requireConsoleSession()
  const [databasesRes, enginesRes] = await Promise.all([
    fetchDegraded<DatabaseRecord[]>("/databases", "Databases", [], { token: session.token }),
    fetchDegraded<DatabaseEngine[]>("/databases/engines", "Engines", [], { token: session.token }),
  ])

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Data"
        title="Databases"
        description="Managed Postgres, MySQL, MariaDB and Redis. Your apps reach them by name on your team's private network; nothing is exposed to the internet. Backups run daily by default."
      />
      <DegradedBanner sources={degradedSources([databasesRes, enginesRes])} />
      <DatabasesManager databases={databasesRes.data} engines={enginesRes.data} />
    </div>
  )
}
