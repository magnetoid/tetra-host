"use client"

import Link from "next/link"
import { useState } from "react"

import { AlertBanner } from "@/components/ui/alert-banner"
import { AppStatus } from "@/components/ui/app-status"
import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/ui/empty-state"
import { useAction } from "@/hooks/use-action"
import { apiFetch } from "@/lib/client-api"
import { faPlus } from "@/lib/icons"
import type { DatabaseEngine, DatabaseEngineKey, DatabaseRecord } from "@/lib/types"

const INPUT =
  "rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/25"

/** Daily at 03:00 UTC is the default; anything else is shown as the cron itself. */
export function describeSchedule(cron: string): string {
  if (!cron) return "Backups off"
  if (cron === "0 3 * * *") return "Daily backups, 03:00 UTC"
  return `Backups: ${cron} (UTC)`
}

export function DatabasesManager({
  databases,
  engines,
}: {
  databases: DatabaseRecord[]
  engines: DatabaseEngine[]
}) {
  const { run, pending, error } = useAction()
  const [name, setName] = useState("")
  const [engine, setEngine] = useState<DatabaseEngineKey>(engines[0]?.key ?? "postgres")
  const selected = engines.find((e) => e.key === engine)
  const [version, setVersion] = useState("")

  async function create(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const ok = await run(
      () =>
        apiFetch("/api/proxy/databases", {
          method: "POST",
          body: { name: name.trim(), engine, version: version || undefined },
          errorMessage: "Could not create the database.",
        }),
      { key: "create", successMessage: `Database ${name.trim()} is starting` },
    )
    if (ok) setName("")
  }

  return (
    <div className="space-y-6">
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}

      <form
        onSubmit={create}
        className="flex flex-wrap items-end gap-3 rounded-lg border border-border bg-muted p-4"
      >
        <label className="block text-sm">
          <span className="mb-2 block text-muted-foreground">Name</span>
          <input
            aria-label="Name"
            value={name}
            onChange={(e) => setName(e.target.value.toLowerCase())}
            placeholder="blog-db"
            pattern="[a-z][a-z0-9-]{1,30}[a-z0-9]"
            title="3–32 characters: lowercase letters, digits and hyphens, starting with a letter"
            className={`${INPUT} w-48 font-mono`}
            required
          />
        </label>
        <label className="block text-sm">
          <span className="mb-2 block text-muted-foreground">Engine</span>
          <select
            aria-label="Engine"
            value={engine}
            onChange={(e) => {
              setEngine(e.target.value as DatabaseEngineKey)
              setVersion("")
            }}
            className={INPUT}
          >
            {engines.map((e) => (
              <option key={e.key} value={e.key}>
                {e.label}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          <span className="mb-2 block text-muted-foreground">Version</span>
          <select
            aria-label="Version"
            value={version || selected?.default_version || ""}
            onChange={(e) => setVersion(e.target.value)}
            className={INPUT}
          >
            {(selected?.versions ?? []).map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
        </label>
        <Button type="submit" variant="primary" icon={faPlus} disabled={pending !== null || !name}>
          {pending === "create" ? "Creating…" : "Create database"}
        </Button>
        {selected && !selected.supports_backup ? (
          <p className="w-full text-xs text-muted-foreground">
            {selected.label} is kept on a volume with append-only persistence; backups are not
            offered for it yet.
          </p>
        ) : null}
      </form>

      {databases.length === 0 ? (
        <EmptyState
          title="No databases yet"
          description="Create one above, then link it to an app: the app gets DATABASE_URL and reaches the database by its name."
        />
      ) : (
        <div className="overflow-hidden rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead className="bg-muted text-left text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Engine</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="hidden px-4 py-3 font-medium md:table-cell">Host</th>
                <th className="hidden px-4 py-3 font-medium md:table-cell">Backups</th>
              </tr>
            </thead>
            <tbody>
              {databases.map((db) => (
                <tr key={db.id} className="border-t border-border">
                  <td className="px-4 py-3">
                    <Link href={`/databases/${db.id}`} className="font-medium hover:underline">
                      {db.name}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {db.engine_label} {db.version}
                  </td>
                  <td className="px-4 py-3">
                    <AppStatus value={db.status} />
                  </td>
                  <td className="hidden px-4 py-3 font-mono text-xs md:table-cell">
                    {db.host}:{db.port}
                  </td>
                  <td className="hidden px-4 py-3 text-muted-foreground md:table-cell">
                    {db.supports_backup ? describeSchedule(db.backup_cron) : "Not offered"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
