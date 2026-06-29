"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"

import { AlertBanner } from "@/components/ui/alert-banner"
import { EmptyState } from "@/components/ui/empty-state"
import { StatusBadge } from "@/components/ui/status-badge"
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
            <ActionButton label="Start" busy={pending === `start:${app.project}`} disabled={pending !== null} onClick={() => act(app.project, "start")} />
            <ActionButton label="Stop" busy={pending === `stop:${app.project}`} disabled={pending !== null} onClick={() => act(app.project, "stop")} />
            <ActionButton label="Remove" tone="danger" busy={pending === `remove:${app.project}`} disabled={pending !== null} onClick={() => act(app.project, "remove")} />
          </div>
        </div>
      ))}
    </div>
  )
}

function ActionButton({
  label,
  busy,
  disabled,
  tone,
  onClick,
}: {
  label: string
  busy: boolean
  disabled: boolean
  tone?: "danger"
  onClick: () => void
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={
        "rounded-md border px-2.5 py-1 text-xs transition disabled:opacity-60 " +
        (tone === "danger"
          ? "border-red-900 text-red-300 hover:bg-red-950"
          : "border-border text-zinc-300 hover:bg-zinc-900")
      }
    >
      {busy ? "…" : label}
    </button>
  )
}
