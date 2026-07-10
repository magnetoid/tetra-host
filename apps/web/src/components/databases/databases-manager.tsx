"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"

import { AlertBanner } from "@/components/ui/alert-banner"
import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/ui/empty-state"
import { StatusBadge } from "@/components/ui/status-badge"
import { faChevronDown, faDatabase, faPlus } from "@/lib/icons"
import type { BackupConfig, DatabaseRecord, DatabaseTargets } from "@/lib/types"
import { cn } from "@/lib/utils"

const INPUT =
  "rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/25"

// The Coolify-supported engines (must match the backend DB_TYPE_ALLOWLIST).
const DB_TYPES = [
  "postgresql", "mysql", "mariadb", "mongodb", "redis", "keydb", "dragonfly", "clickhouse",
]

export function DatabasesManager({
  databases,
  targets,
}: {
  databases: DatabaseRecord[]
  targets: DatabaseTargets
}) {
  const router = useRouter()
  const [pending, setPending] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [backups, setBackups] = useState<Record<string, BackupConfig[]>>({})

  // Provision form
  const [dbType, setDbType] = useState(DB_TYPES[0])
  const [name, setName] = useState("")
  const [server, setServer] = useState(targets.servers[0]?.uuid ?? "")
  const [project, setProject] = useState(targets.projects[0]?.uuid ?? "")

  async function provision(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setPending("provision")
    setError(null)
    setNotice(null)
    try {
      const res = await fetch("/api/proxy/databases", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          db_type: dbType, name, server_uuid: server,
          project_uuid: project, environment_name: "production",
        }),
      })
      const payload = (await res.json().catch(() => ({}))) as { detail?: string; message?: string }
      if (!res.ok) {
        setError(payload.detail ?? "Provisioning failed.")
        return
      }
      setNotice(payload.message ?? "Database provisioned.")
      setName("")
      router.refresh()
    } catch {
      setError("Unable to reach the control plane.")
    } finally {
      setPending(null)
    }
  }

  async function toggle(dbId: string) {
    const next = expandedId === dbId ? null : dbId
    setExpandedId(next)
    if (next && backups[dbId] === undefined) {
      try {
        const res = await fetch(`/api/proxy/databases/${dbId}/backups`)
        const rows = res.ok ? ((await res.json()) as BackupConfig[]) : []
        setBackups((b) => ({ ...b, [dbId]: Array.isArray(rows) ? rows : [] }))
      } catch {
        setBackups((b) => ({ ...b, [dbId]: [] }))
      }
    }
  }

  async function scheduleBackup(dbId: string, form: HTMLFormElement) {
    const data = new FormData(form)
    setPending(`backup:${dbId}`)
    setError(null)
    setNotice(null)
    try {
      const res = await fetch(`/api/proxy/databases/${dbId}/backups`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          frequency: String(data.get("frequency") || "0 2 * * *"),
          retention_days: Number(data.get("retention_days") || 7),
          s3_storage_id: String(data.get("s3_storage_id") || ""),
        }),
      })
      const payload = (await res.json().catch(() => ({}))) as { detail?: string; message?: string }
      if (!res.ok) {
        setError(payload.detail ?? "Could not schedule backup.")
        return
      }
      setNotice(payload.message ?? "Backup scheduled.")
      // Refresh this db's backup list.
      const list = await fetch(`/api/proxy/databases/${dbId}/backups`)
      const rows = list.ok ? ((await list.json()) as BackupConfig[]) : null
      if (rows) setBackups((b) => ({ ...b, [dbId]: rows }))
    } catch {
      setError("Unable to reach the control plane.")
    } finally {
      setPending(null)
    }
  }

  const canProvision = Boolean(name && server && project)

  return (
    <div className="space-y-6">
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}
      {notice ? <AlertBanner tone="success">{notice}</AlertBanner> : null}

      <form
        onSubmit={provision}
        className="flex flex-wrap items-end gap-3 rounded-2xl border border-border bg-muted p-4"
      >
        <label className="block text-sm">
          <span className="mb-2 block text-muted-foreground">Engine</span>
          <select
            aria-label="Engine"
            value={dbType}
            onChange={(e) => setDbType(e.target.value)}
            className={INPUT}
          >
            {DB_TYPES.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </label>
        <label className="block flex-1 text-sm">
          <span className="mb-2 block text-muted-foreground">Name</span>
          <input
            aria-label="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="my-db"
            className={`${INPUT} w-full`}
            required
          />
        </label>
        <label className="block text-sm">
          <span className="mb-2 block text-muted-foreground">Server</span>
          <select
            aria-label="Server"
            value={server}
            onChange={(e) => setServer(e.target.value)}
            className={INPUT}
          >
            {targets.servers.length === 0 ? <option value="">no servers</option> : null}
            {targets.servers.map((s) => (
              <option key={s.uuid} value={s.uuid}>{s.name}</option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          <span className="mb-2 block text-muted-foreground">Project</span>
          <select
            aria-label="Project"
            value={project}
            onChange={(e) => setProject(e.target.value)}
            className={INPUT}
          >
            {targets.projects.length === 0 ? <option value="">no projects</option> : null}
            {targets.projects.map((p) => (
              <option key={p.uuid} value={p.uuid}>{p.name}</option>
            ))}
          </select>
        </label>
        <Button type="submit" icon={faPlus} disabled={pending !== null || !canProvision}>
          {pending === "provision" ? "…" : "Provision"}
        </Button>
      </form>

      {databases.length === 0 ? (
        <EmptyState
          title="No databases yet"
          description="Provision a managed Postgres, MySQL, Redis, Mongo (and more) above — with scheduled S3 backups."
        />
      ) : (
        <div className="space-y-3">
          {databases.map((db) => {
            const expanded = expandedId === db.id
            const list = backups[db.id]
            return (
              <div
                key={db.id}
                className={cn(
                  "overflow-hidden rounded-2xl border bg-muted transition-colors",
                  expanded ? "border-primary/40" : "border-border hover:border-primary/30",
                )}
              >
                <button
                  type="button"
                  onClick={() => toggle(db.id)}
                  aria-expanded={expanded}
                  className="flex w-full flex-wrap items-center justify-between gap-3 p-4 text-left"
                >
                  <div className="flex min-w-0 items-center gap-2">
                    <FontAwesomeIcon
                      icon={faChevronDown}
                      className={cn(
                        "h-3 w-3 shrink-0 text-muted-foreground transition-transform",
                        expanded && "rotate-180",
                      )}
                    />
                    <FontAwesomeIcon icon={faDatabase} className="h-3.5 w-3.5 shrink-0 text-primary" />
                    <span className="truncate font-medium">{db.name}</span>
                    <span className="rounded-full border border-border bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                      {db.type || "db"}
                    </span>
                    <StatusBadge value={db.status} />
                  </div>
                </button>

                {expanded ? (
                  <div className="space-y-4 border-t border-border px-4 pb-4 pt-4">
                    {db.internal_db_url ? (
                      <div>
                        <div className="mb-1 text-xs text-muted-foreground">Internal connection</div>
                        <code className="block overflow-x-auto rounded-lg border border-border bg-background px-3 py-2 font-mono text-xs">
                          {db.internal_db_url}
                        </code>
                      </div>
                    ) : null}

                    <div>
                      <div className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                        Scheduled backups
                      </div>
                      {list === undefined ? (
                        <p className="text-sm text-muted-foreground">Loading…</p>
                      ) : list.length === 0 ? (
                        <p className="text-sm text-muted-foreground">No backups scheduled yet.</p>
                      ) : (
                        <ul className="space-y-2">
                          {list.map((b) => (
                            <li
                              key={b.id}
                              className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-background px-3 py-2 text-sm"
                            >
                              <span className="font-mono text-xs">{b.frequency || "—"}</span>
                              <span className="text-xs text-muted-foreground">
                                keep {b.retention_days}d
                                {b.s3_storage_id ? " · S3" : " · local"}
                              </span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>

                    <form
                      onSubmit={(e) => {
                        e.preventDefault()
                        void scheduleBackup(db.id, e.currentTarget)
                      }}
                      className="flex flex-wrap items-end gap-3 rounded-xl border border-border bg-background p-3"
                    >
                      <label className="block text-sm">
                        <span className="mb-1 block text-xs text-muted-foreground">Frequency (cron)</span>
                        <input name="frequency" defaultValue="0 2 * * *" className={INPUT} aria-label="Frequency" />
                      </label>
                      <label className="block text-sm">
                        <span className="mb-1 block text-xs text-muted-foreground">Retention (days)</span>
                        <input name="retention_days" type="number" min={1} defaultValue={7} className={`${INPUT} w-28`} aria-label="Retention days" />
                      </label>
                      <label className="block flex-1 text-sm">
                        <span className="mb-1 block text-xs text-muted-foreground">S3 storage UUID (optional)</span>
                        <input name="s3_storage_id" placeholder="local if empty" className={`${INPUT} w-full`} aria-label="S3 storage UUID" />
                      </label>
                      <Button type="submit" size="sm" icon={faPlus} disabled={pending !== null}>
                        {pending === `backup:${db.id}` ? "…" : "Schedule"}
                      </Button>
                    </form>
                  </div>
                ) : null}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
