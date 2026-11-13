import Link from "next/link"

import { DatabaseBackups } from "@/components/databases/database-backups"
import { DatabaseControls } from "@/components/databases/database-controls"
import { DatabaseConnect } from "@/components/databases/database-connect"
import { AppStatus } from "@/components/ui/app-status"
import { DegradedBanner } from "@/components/ui/degraded-banner"
import { PageHeader } from "@/components/ui/page-header"
import { requireConsoleSession } from "@/lib/auth"
import { degradedSources, fetchDegraded } from "@/lib/fetch-degraded"
import type { DatabaseBackupRecord, DatabaseRecord, InstalledApp } from "@/lib/types"

export default async function DatabasePage({ params }: { params: Promise<{ id: string }> }) {
  const session = await requireConsoleSession()
  const { id } = await params
  const opts = { token: session.token }

  const [dbRes, backupsRes, appsRes] = await Promise.all([
    fetchDegraded<DatabaseRecord | null>(`/databases/${id}`, "Database", null, opts),
    fetchDegraded<DatabaseBackupRecord[]>(`/databases/${id}/backups`, "Backups", [], opts),
    fetchDegraded<InstalledApp[]>("/apps", "Apps", [], opts),
  ])
  const db = dbRes.data

  if (!db) {
    return (
      <div className="space-y-6">
        <Link href="/databases" className="text-sm text-muted-foreground hover:text-foreground">
          ← Databases
        </Link>
        <DegradedBanner sources={degradedSources([dbRes])} />
        <p className="text-sm text-muted-foreground">This database doesn&apos;t exist or isn&apos;t yours.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <Link href="/databases" className="text-sm text-muted-foreground hover:text-foreground">
        ← Databases
      </Link>
      <PageHeader
        eyebrow={`${db.engine_label} ${db.version}`}
        title={db.name}
        description={`Reachable from your apps at ${db.host}:${db.port}, on your team's private network only.`}
        action={<DatabaseControls database={db} />}
      />
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <AppStatus value={db.status} />
      </div>
      <DegradedBanner sources={degradedSources([dbRes, backupsRes, appsRes])} />
      <DatabaseConnect database={db} apps={appsRes.data} />
      <DatabaseBackups database={db} backups={backupsRes.data} />
    </div>
  )
}
