"use client"

import { useEffect, useRef, useState } from "react"

import { AlertBanner } from "@/components/ui/alert-banner"
import { cn } from "@/lib/utils"

const LINE_CHOICES = [100, 200, 500, 1000]
const POLL_MS = 5000

/**
 * Live container (runtime) output for a project, polled from the backend's
 * /projects/{id}/logs snapshot endpoint. Pauses polling on demand and autoscrolls
 * while live. Distinct from the per-deployment *build* logs in DeployConsole.
 */
export function RuntimeLogs({ projectId }: { projectId: string }) {
  const [logs, setLogs] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [live, setLive] = useState(true)
  const [lines, setLines] = useState(200)
  const preRef = useRef<HTMLPreElement>(null)

  useEffect(() => {
    let cancelled = false

    // setState lives inside the promise callbacks (never the synchronous effect
    // body) so a poll tick can't trigger a cascading render.
    const tick = () => {
      fetch(`/api/proxy/projects/${projectId}/logs?lines=${lines}`)
        .then(async (res) => {
          if (cancelled) return
          if (!res.ok) {
            const payload = (await res.json().catch(() => ({}))) as { detail?: string }
            if (!cancelled) setError(payload.detail ?? `Failed to load logs (${res.status}).`)
            return
          }
          const data = (await res.json()) as { logs?: string }
          if (cancelled) return
          setError(null)
          setLogs(data.logs ?? "")
        })
        .catch(() => {
          if (!cancelled) setError("Unable to reach the control plane.")
        })
        .finally(() => {
          if (!cancelled) setLoading(false)
        })
    }

    tick()
    if (!live) {
      return () => {
        cancelled = true
      }
    }
    const timer = setInterval(tick, POLL_MS)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [projectId, lines, live])

  useEffect(() => {
    if (live && preRef.current) {
      preRef.current.scrollTop = preRef.current.scrollHeight
    }
  }, [logs, live])

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => setLive((v) => !v)}
          className={cn(
            "inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm transition-colors",
            live
              ? "border-status-ok/25 bg-status-ok/10 text-status-ok"
              : "border-border text-muted-foreground hover:bg-accent",
          )}
        >
          <span
            className={cn(
              "h-2 w-2 rounded-full",
              live ? "animate-pulse bg-status-ok" : "bg-muted-foreground",
            )}
          />
          {live ? "Live" : "Paused"}
        </button>
        <select
          value={lines}
          onChange={(e) => setLines(Number(e.target.value))}
          className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
          aria-label="Number of log lines"
        >
          {LINE_CHOICES.map((n) => (
            <option key={n} value={n}>
              {n} lines
            </option>
          ))}
        </select>
      </div>

      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}

      <pre
        ref={preRef}
        className="max-h-[28rem] overflow-auto whitespace-pre-wrap break-words rounded-lg border border-border bg-black/60 p-4 font-mono text-xs leading-relaxed text-zinc-300"
      >
        {loading ? "Loading…" : logs.trim() ? logs : "(no runtime output)"}
      </pre>
    </div>
  )
}
