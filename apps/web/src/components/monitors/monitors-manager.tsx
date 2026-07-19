"use client"

import { useRouter } from "next/navigation"
import { useState } from "react"

import { AlertBanner } from "@/components/ui/alert-banner"
import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/ui/empty-state"
import { useAction } from "@/hooks/use-action"
import { apiFetch } from "@/lib/client-api"
import { faArrowsRotate, faPlus, faTrash } from "@/lib/icons"
import type { UptimeMonitorSummary } from "@/lib/types"

const INPUT =
  "rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/25"

function StatusPill({ status }: { status: string }) {
  const tone =
    status === "up"
      ? "bg-status-ok/10 text-status-ok"
      : status === "down"
        ? "bg-status-err/10 text-status-err"
        : "bg-muted text-muted-foreground"
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${tone}`}>
      <span className="size-1.5 rounded-full bg-current" />
      {status === "up" ? "Up" : status === "down" ? "Down" : "Unknown"}
    </span>
  )
}

/**
 * Uptime monitors (parity with `tetra monitors …`). The platform probes each URL
 * every minute and fires app.down / app.up via notification channels; here you can
 * add, probe on demand, and delete. Mirrors the jobs/tokens manager pattern.
 */
export function MonitorsManager({ monitors }: { monitors: UptimeMonitorSummary[] }) {
  const router = useRouter()
  const { run, pending, error } = useAction()
  const [name, setName] = useState("")
  const [url, setUrl] = useState("")

  async function create(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const ok = await run(
      () =>
        apiFetch("/api/proxy/account/monitors", {
          method: "POST",
          body: { name, url },
          errorMessage: "Could not create monitor.",
        }),
      { key: "create", successMessage: "Monitor added" },
    )
    if (ok) {
      setName("")
      setUrl("")
      router.refresh()
    }
  }

  function check(id: string) {
    return run(
      async () => {
        await apiFetch(`/api/proxy/account/monitors/${id}/check`, {
          method: "POST",
          errorMessage: "Probe failed.",
        })
        router.refresh()
      },
      { key: `check:${id}` },
    )
  }

  function remove(id: string) {
    return run(
      async () => {
        await apiFetch(`/api/proxy/account/monitors/${id}`, {
          method: "DELETE",
          errorMessage: "Could not delete monitor.",
        })
        router.refresh()
      },
      { key: `rm:${id}`, successMessage: "Monitor deleted" },
    )
  }

  return (
    <div className="space-y-4">
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}

      <form onSubmit={create} className="flex flex-wrap items-end gap-3 rounded-lg border border-border bg-muted p-4">
        <label className="block text-sm">
          <span className="mb-2 block text-muted-foreground">Name</span>
          <input
            aria-label="Monitor name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="marketing-site"
            className={`${INPUT} w-44`}
            required
          />
        </label>
        <label className="block flex-1 text-sm">
          <span className="mb-2 block text-muted-foreground">URL to probe</span>
          <input
            aria-label="Monitor URL"
            type="url"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://example.com/health"
            className={`${INPUT} w-full`}
            required
          />
        </label>
        <Button type="submit" icon={faPlus} disabled={pending !== null}>
          {pending === "create" ? "…" : "Add monitor"}
        </Button>
      </form>

      {monitors.length === 0 ? (
        <EmptyState
          title="No monitors yet"
          description="Add a URL and Tetra will probe it every minute, alerting your notification channels when it goes down or recovers."
        />
      ) : (
        <div className="space-y-2">
          {monitors.map((monitor) => (
            <div
              key={monitor.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-muted px-4 py-3"
            >
              <div className="flex min-w-0 items-center gap-3 text-sm">
                <StatusPill status={monitor.status} />
                <span className="font-medium">{monitor.name}</span>
                <span className="truncate font-mono text-xs text-muted-foreground">{monitor.url}</span>
                {monitor.last_checked_at ? (
                  <span className="font-mono text-xs text-muted-foreground">
                    {monitor.last_latency_ms}ms · {monitor.last_detail}
                  </span>
                ) : null}
              </div>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="secondary"
                  icon={faArrowsRotate}
                  disabled={pending !== null}
                  onClick={() => check(monitor.id)}
                >
                  {pending === `check:${monitor.id}` ? "…" : "Check now"}
                </Button>
                <Button
                  size="sm"
                  variant="danger"
                  icon={faTrash}
                  disabled={pending !== null}
                  onClick={() => remove(monitor.id)}
                >
                  {pending === `rm:${monitor.id}` ? "…" : "Delete"}
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
