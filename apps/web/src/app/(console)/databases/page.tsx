import { DatabasesManager } from "@/components/databases/databases-manager"
import { PageHeader } from "@/components/ui/page-header"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { DatabaseRecord, DatabaseTargets } from "@/lib/types"

const EMPTY_TARGETS: DatabaseTargets = { servers: [], projects: [] }

export default async function DatabasesPage() {
  const session = await requireConsoleSession()

  const [databases, targets] = await Promise.all([
    fetchBackend<DatabaseRecord[]>("/databases", { token: session.token }).catch(
      () => [] as DatabaseRecord[],
    ),
    fetchBackend<DatabaseTargets>("/databases/targets", { token: session.token }).catch(
      () => EMPTY_TARGETS,
    ),
  ])

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Data"
        title="Databases"
        description="Provision managed databases and schedule S3 backups. Postgres, MySQL, MariaDB, Mongo, Redis, KeyDB, Dragonfly, ClickHouse."
      />
      <DatabasesManager databases={databases} targets={targets} />
    </div>
  )
}
