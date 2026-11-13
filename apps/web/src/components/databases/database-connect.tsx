"use client"

import { useState } from "react"
import { toast } from "sonner"

import { AlertBanner } from "@/components/ui/alert-banner"
import { Button } from "@/components/ui/button"
import { useAction } from "@/hooks/use-action"
import { apiFetch } from "@/lib/client-api"
import { faCopy, faEye, faLink } from "@/lib/icons"
import type { DatabaseConnection, DatabaseRecord, InstalledApp } from "@/lib/types"

const INPUT =
  "rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/25"

/** Reveal/copy the connection URL, and put it on one of the team's apps as an env var. */
export function DatabaseConnect({
  database,
  apps,
}: {
  database: DatabaseRecord
  apps: InstalledApp[]
}) {
  const { run, pending, error } = useAction()
  const [connection, setConnection] = useState<DatabaseConnection | null>(null)
  const [project, setProject] = useState(apps[0]?.project ?? "")
  const [key, setKey] = useState("DATABASE_URL")
  const base = `/api/proxy/databases/${encodeURIComponent(database.id)}`

  async function reveal() {
    await run(
      async () => {
        setConnection(
          await apiFetch<DatabaseConnection>(`${base}/connection`, {
            errorMessage: "Could not load the connection details.",
          }),
        )
      },
      { key: "reveal", refresh: false },
    )
  }

  async function copy() {
    if (!connection) return
    await navigator.clipboard.writeText(connection.url)
    toast.success("Connection URL copied")
  }

  function link(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    return run(
      () =>
        apiFetch(`${base}/link`, {
          method: "POST",
          body: { project, key },
          errorMessage: "Could not link the database.",
        }),
      { key: "link", successMessage: `${key} set on ${project}. Redeploy it to apply.` },
    )
  }

  return (
    <section className="space-y-4 rounded-lg border border-border bg-muted p-5">
      <div>
        <h2 className="text-base font-semibold">Connect</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Apps deployed by your team reach this database at{" "}
          <span className="font-mono text-foreground">
            {database.host}:{database.port}
          </span>
          . It has no public address.
        </p>
      </div>
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}

      {connection ? (
        <div className="flex flex-wrap items-center gap-2">
          <code className="min-w-0 flex-1 truncate rounded-md border border-border bg-background px-3 py-2 font-mono text-xs">
            {connection.url}
          </code>
          <Button size="sm" icon={faCopy} onClick={copy}>
            Copy
          </Button>
        </div>
      ) : (
        <Button size="sm" icon={faEye} disabled={pending !== null} onClick={reveal}>
          {pending === "reveal" ? "…" : "Show connection URL"}
        </Button>
      )}

      <form onSubmit={link} className="flex flex-wrap items-end gap-3 border-t border-border pt-4">
        <label className="block text-sm">
          <span className="mb-2 block text-muted-foreground">App</span>
          <select
            aria-label="App"
            value={project}
            onChange={(e) => setProject(e.target.value)}
            className={INPUT}
            disabled={apps.length === 0}
          >
            {apps.length === 0 ? <option value="">No apps yet</option> : null}
            {apps.map((a) => (
              <option key={a.project} value={a.project}>
                {a.name || a.project}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          <span className="mb-2 block text-muted-foreground">Variable</span>
          <input
            aria-label="Variable"
            value={key}
            onChange={(e) => setKey(e.target.value.toUpperCase())}
            className={`${INPUT} w-48 font-mono`}
            required
          />
        </label>
        <Button type="submit" icon={faLink} disabled={pending !== null || !project || !key}>
          {pending === "link" ? "…" : "Link to app"}
        </Button>
        <p className="w-full text-xs text-muted-foreground">
          Stores the URL as a secret variable on the app. It takes effect on the app&apos;s next
          deploy, which also joins it to the private network.
        </p>
      </form>
    </section>
  )
}
