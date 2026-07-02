"use client"

import { useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"

import { AlertBanner } from "@/components/ui/alert-banner"
import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/ui/empty-state"
import { StatusBadge } from "@/components/ui/status-badge"
import { faCirclePlay, faCircleStop, faTrash } from "@/lib/icons"
import type { InstalledApp } from "@/lib/types"

export function InstalledApps({ apps }: { apps: InstalledApp[] }) {
  const router = useRouter()
  const [pending, setPending] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function act(project: string, verb: "start" | "stop" | "remove") {
    setPending(`${verb}:${project}`)
    setError(null)
    const method = verb === "remove" ? "DELETE" : "POST"
    const path = verb === "remove" ? `apps/${project}` : `apps/${project}/${verb}`
    try {
      const response = await fetch(`/api/proxy/${path}`, { method })
      const payload = (await response.json().catch(() => ({}))) as { detail?: string }
      if (!response.ok) {
        setError(payload.detail ?? "Action failed.")
        return
      }
      router.refresh()
    } catch {
      setError("Unable to reach the control plane.")
    } finally {
      setPending(null)
    }
  }

  if (apps.length === 0) {
    return <EmptyState title="No apps installed yet." description="Pick one from the marketplace below." />
  }

  return (
    <div className="space-y-3">
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}
      {apps.map((app) => (
        <div
          key={app.project}
          className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-border bg-muted p-4"
        >
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-medium">{app.name}</span>
              <StatusBadge value={app.status} />
            </div>
            <div className="mt-1 text-sm text-zinc-500">
              {app.domain ? (
                <a href={`https://${app.domain}`} target="_blank" rel="noreferrer" className="hover:text-zinc-300">
                  {app.domain}
                </a>
              ) : (
                <span className="font-mono text-xs">{app.project}</span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Link
              href={`/apps/${app.project}/compute`}
              className="rounded-md border border-border px-3 py-1.5 text-sm text-zinc-300 transition hover:bg-white/5"
            >
              Compute
            </Link>
            <Button size="sm" icon={faCirclePlay} disabled={pending !== null} onClick={() => act(app.project, "start")}>
              {pending === `start:${app.project}` ? "…" : "Start"}
            </Button>
            <Button size="sm" icon={faCircleStop} disabled={pending !== null} onClick={() => act(app.project, "stop")}>
              {pending === `stop:${app.project}` ? "…" : "Stop"}
            </Button>
            <Button size="sm" variant="danger" icon={faTrash} disabled={pending !== null} onClick={() => act(app.project, "remove")}>
              {pending === `remove:${app.project}` ? "…" : "Remove"}
            </Button>
          </div>
        </div>
      ))}
    </div>
  )
}
