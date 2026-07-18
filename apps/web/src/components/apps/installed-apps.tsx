"use client"

import Link from "next/link"

import { AlertBanner } from "@/components/ui/alert-banner"
import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/ui/empty-state"
import { StatusBadge } from "@/components/ui/status-badge"
import { useAction } from "@/hooks/use-action"
import { apiFetch } from "@/lib/client-api"
import { faCirclePlay, faCircleStop, faTrash } from "@/lib/icons"
import type { InstalledApp } from "@/lib/types"

const ACT_DONE: Record<"start" | "stop" | "remove", string> = {
  start: "App started",
  stop: "App stopped",
  remove: "App removed",
}

export function InstalledApps({ apps }: { apps: InstalledApp[] }) {
  const { run, pending, error } = useAction()

  function act(project: string, verb: "start" | "stop" | "remove") {
    const method = verb === "remove" ? "DELETE" : "POST"
    const path = verb === "remove" ? `apps/${project}` : `apps/${project}/${verb}`
    return run(
      () => apiFetch(`/api/proxy/${path}`, { method, errorMessage: "Action failed." }),
      { key: `${verb}:${project}`, successMessage: ACT_DONE[verb] },
    )
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
          className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-muted p-4"
        >
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-medium">{app.name}</span>
              <StatusBadge value={app.status} />
            </div>
            <div className="mt-1 text-sm text-muted-foreground">
              {app.domain ? (
                <a href={`https://${app.domain}`} target="_blank" rel="noreferrer" className="font-mono hover:text-foreground">
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
              className="rounded-md border border-border px-3 py-1.5 text-sm text-foreground transition-colors hover:bg-accent"
            >
              Compute
            </Link>
            <Link
              href={`/apps/${app.project}/env`}
              className="rounded-md border border-border px-3 py-1.5 text-sm text-foreground transition-colors hover:bg-accent"
            >
              Env
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
