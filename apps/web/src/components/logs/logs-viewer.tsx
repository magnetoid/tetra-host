"use client"

import { useMemo, useState } from "react"

import { AlertBanner } from "@/components/ui/alert-banner"
import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/ui/empty-state"
import { faArrowsRotate } from "@/lib/icons"
import type { InstalledApp } from "@/lib/types"

const CONTROL =
  "rounded-lg border border-border bg-background px-2.5 py-1.5 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/25"

export function LogsViewer({ apps }: { apps: InstalledApp[] }) {
  const [project, setProject] = useState(apps[0]?.project ?? "")
  const [raw, setRaw] = useState("")
  const [filter, setFilter] = useState("")
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loadedFor, setLoadedFor] = useState<string | null>(null)

  async function load(target: string) {
    if (!target) return
    setPending(true)
    setError(null)
    try {
      const res = await fetch(`/api/proxy/apps/${target}/logs`)
      const payload = (await res.json().catch(() => ({}))) as { logs?: string; detail?: string }
      if (!res.ok) {
        setError(payload.detail ?? "Could not load logs.")
        return
      }
      setRaw(payload.logs ?? "")
      setLoadedFor(target)
    } catch {
      setError("Unable to reach the control plane.")
    } finally {
      setPending(false)
    }
  }

  const lines = useMemo(() => {
    const all = raw.split("\n")
    const needle = filter.trim().toLowerCase()
    return needle ? all.filter((l) => l.toLowerCase().includes(needle)) : all
  }, [raw, filter])

  if (apps.length === 0) {
    return (
      <EmptyState
        title="No apps to show logs for"
        description="Install a marketplace app or deploy a project to stream its runtime logs here."
      />
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-sm">
          <span className="text-muted-foreground">App</span>
          <select
            aria-label="App"
            value={project}
            onChange={(e) => {
              setProject(e.target.value)
              void load(e.target.value)
            }}
            className={CONTROL}
          >
            {apps.map((a) => (
              <option key={a.project} value={a.project}>{a.name || a.project}</option>
            ))}
          </select>
        </label>
        <input
          aria-label="Filter"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter lines…"
          className={`${CONTROL} flex-1`}
        />
        <Button
          size="sm"
          icon={faArrowsRotate}
          disabled={pending || !project}
          onClick={() => load(project)}
        >
          {pending ? "…" : loadedFor ? "Refresh" : "Load"}
        </Button>
      </div>

      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}

      <div className="h-[32rem] overflow-auto rounded-lg border border-border bg-black/70 p-4 font-mono text-xs leading-relaxed text-zinc-300">
        {loadedFor === null ? (
          <div className="text-zinc-500">Select an app and load its logs.</div>
        ) : lines.length === 0 || (lines.length === 1 && lines[0] === "") ? (
          <div className="text-zinc-500">
            {filter ? "No lines match the filter." : "No logs yet."}
          </div>
        ) : (
          lines.map((line, i) => (
            <div key={i} className="whitespace-pre-wrap break-all">
              {line || " "}
            </div>
          ))
        )}
      </div>
      {loadedFor ? (
        <div className="text-xs text-muted-foreground">
          {filter ? `${lines.length} matching line(s)` : `${lines.length} line(s)`} · {loadedFor}
        </div>
      ) : null}
    </div>
  )
}
