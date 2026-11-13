"use client"

import { useRouter } from "next/navigation"
import { useEffect, useState } from "react"

import { AlertBanner } from "@/components/ui/alert-banner"
import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/ui/empty-state"
import { Modal } from "@/components/ui/modal"
import { useAction } from "@/hooks/use-action"
import { apiFetch } from "@/lib/client-api"
import { faDatabase, faRotateLeft, faTrash } from "@/lib/icons"
import type { DatabaseBackupRecord, DatabaseRecord } from "@/lib/types"
import { cn, formatBytes, formatRelativeLabel } from "@/lib/utils"

import { describeSchedule } from "./databases-manager"

const INPUT =
  "rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/25"

const TONE: Record<string, string> = {
  ok: "text-status-ok",
  error: "text-status-err",
  running: "text-status-live",
}

/** True while any backup or restore of this database is still running. */
export function hasRunningOperation(backups: DatabaseBackupRecord[]): boolean {
  return backups.some((b) => b.status === "running" || b.restore_status === "running")
}

export function DatabaseBackups({
  database,
  backups,
}: {
  database: DatabaseRecord
  backups: DatabaseBackupRecord[]
}) {
  const router = useRouter()
  const { run, pending, error } = useAction()
  const [cron, setCron] = useState(database.backup_cron)
  const [keep, setKeep] = useState(String(database.backup_keep))
  const [restoring, setRestoring] = useState<DatabaseBackupRecord | null>(null)
  const base = `/api/proxy/databases/${encodeURIComponent(database.id)}`
  const busy = hasRunningOperation(backups)

  // Poll while a backup or restore runs, so the outcome appears without a reload.
  useEffect(() => {
    if (!busy) return
    const timer = setInterval(() => router.refresh(), 3000)
    return () => clearInterval(timer)
  }, [busy, router])

  if (!database.supports_backup) {
    return (
      <section className="rounded-lg border border-border bg-muted p-5">
        <h2 className="text-base font-semibold">Backups</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {database.engine_label} keeps its data on a volume with append-only persistence. Backups
          aren&apos;t offered for it yet.
        </p>
      </section>
    )
  }

  function saveSchedule(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    return run(
      () =>
        apiFetch(base, {
          method: "PATCH",
          body: { backup_cron: cron.trim(), backup_keep: Number(keep) },
          errorMessage: "Could not save the schedule.",
        }),
      { key: "schedule", successMessage: "Backup schedule saved" },
    )
  }

  async function restore() {
    if (!restoring) return
    const ok = await run(
      () =>
        apiFetch(`${base}/backups/${restoring.id}/restore`, {
          method: "POST",
          errorMessage: "Could not start the restore.",
        }),
      { key: "restore", successMessage: "Restore started" },
    )
    if (ok) setRestoring(null)
  }

  return (
    <section className="space-y-4 rounded-lg border border-border bg-muted p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold">Backups</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {describeSchedule(database.backup_cron)}, keeping the last {database.backup_keep}.
            Manual backups are kept until you delete them.
          </p>
        </div>
        <Button
          size="sm"
          variant="primary"
          icon={faDatabase}
          disabled={pending !== null || busy}
          onClick={() =>
            run(
              () =>
                apiFetch(`${base}/backups`, {
                  method: "POST",
                  errorMessage: "Could not start a backup.",
                }),
              { key: "backup", successMessage: "Backup started" },
            )
          }
        >
          {pending === "backup" ? "…" : "Back up now"}
        </Button>
      </div>
      {error && !restoring ? <AlertBanner tone="error">{error}</AlertBanner> : null}

      <form onSubmit={saveSchedule} className="flex flex-wrap items-end gap-3">
        <label className="block text-sm">
          <span className="mb-2 block text-muted-foreground">Schedule (cron, UTC; empty = off)</span>
          <input
            aria-label="Schedule"
            value={cron}
            onChange={(e) => setCron(e.target.value)}
            placeholder="0 3 * * *"
            className={`${INPUT} w-44 font-mono`}
          />
        </label>
        <label className="block text-sm">
          <span className="mb-2 block text-muted-foreground">Keep</span>
          <input
            aria-label="Keep"
            type="number"
            min={1}
            max={90}
            value={keep}
            onChange={(e) => setKeep(e.target.value)}
            className={`${INPUT} w-24`}
          />
        </label>
        <Button type="submit" size="sm" disabled={pending !== null}>
          {pending === "schedule" ? "…" : "Save schedule"}
        </Button>
      </form>

      {backups.length === 0 ? (
        <EmptyState
          title="No backups yet"
          description="The first scheduled backup runs tonight, or back up now."
        />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border bg-background">
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-4 py-3 font-medium">Taken</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="hidden px-4 py-3 font-medium md:table-cell">Size</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {backups.map((b) => (
                <tr key={b.id} className="border-t border-border align-top">
                  <td className="px-4 py-3">
                    <div>{formatRelativeLabel(b.created_at)}</div>
                    <div className="text-xs text-muted-foreground">{b.trigger}</div>
                  </td>
                  <td className="px-4 py-3">
                    <span className={cn("font-medium", TONE[b.status])}>{b.status}</span>
                    {b.error ? (
                      <div className="max-w-[16rem] truncate text-xs text-muted-foreground" title={b.error}>
                        {b.error}
                      </div>
                    ) : null}
                    {b.restore_status ? (
                      <div
                        className="max-w-[16rem] truncate text-xs text-muted-foreground"
                        title={b.restore_error || undefined}
                      >
                        restore{" "}
                        <span className={cn("font-medium", TONE[b.restore_status])}>
                          {b.restore_status}
                        </span>
                        {b.restored_at ? ` · ${formatRelativeLabel(b.restored_at)}` : ""}
                        {b.restore_error ? ` · ${b.restore_error}` : ""}
                      </div>
                    ) : null}
                  </td>
                  <td className="hidden whitespace-nowrap px-4 py-3 text-muted-foreground md:table-cell">
                    {b.status === "ok" ? formatBytes(b.size_bytes) : "—"}
                  </td>
                  <td className="w-px whitespace-nowrap px-4 py-3">
                    <div className="flex justify-end gap-1">
                      <Button
                        size="sm"
                        icon={faRotateLeft}
                        disabled={pending !== null || busy || b.status !== "ok"}
                        onClick={() => setRestoring(b)}
                      >
                        Restore
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        icon={faTrash}
                        aria-label="Delete backup"
                        disabled={pending !== null || b.status === "running" || b.restore_status === "running"}
                        onClick={() =>
                          run(
                            () =>
                              apiFetch(`${base}/backups/${b.id}`, {
                                method: "DELETE",
                                errorMessage: "Could not delete the backup.",
                              }),
                            { key: `rm:${b.id}`, successMessage: "Backup deleted" },
                          )
                        }
                      />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal
        open={restoring !== null}
        onOpenChange={(open) => (open ? null : setRestoring(null))}
        title={`Restore ${database.name}?`}
        description={
          restoring
            ? `The data in ${database.name} is replaced with the backup taken ${formatRelativeLabel(restoring.created_at)}. Changes made since then are lost. Back up first if you might need them.`
            : undefined
        }
        footer={
          <div className="flex justify-end gap-2">
            <Button onClick={() => setRestoring(null)}>Cancel</Button>
            <Button variant="destructive" disabled={pending !== null} onClick={restore}>
              {pending === "restore" ? "Starting…" : "Restore"}
            </Button>
          </div>
        }
      >
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Apps stay connected while the restore runs; pause writes if you can.
          </p>
          {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}
        </div>
      </Modal>
    </section>
  )
}
