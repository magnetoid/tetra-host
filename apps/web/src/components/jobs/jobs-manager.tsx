"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"

import { AlertBanner } from "@/components/ui/alert-banner"
import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/ui/empty-state"
import { faPlus, faTrash } from "@/lib/icons"
import type { JobRunRecord, ScheduledJobRecord } from "@/lib/types"
import { cn, formatRelativeLabel } from "@/lib/utils"

const INPUT =
  "rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/25"

const STATUS_TONE: Record<string, string> = {
  ok: "text-status-ok",
  error: "text-status-err",
}

export function JobsManager({ jobs }: { jobs: ScheduledJobRecord[] }) {
  const router = useRouter()
  const [name, setName] = useState("")
  const [cron, setCron] = useState("*/5 * * * *")
  const [url, setUrl] = useState("")
  const [method, setMethod] = useState("GET")
  const [pending, setPending] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [runs, setRuns] = useState<Record<string, JobRunRecord[]>>({})

  async function create(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setPending("create")
    setError(null)
    try {
      const res = await fetch("/api/proxy/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, cron, url, method }),
      })
      const payload = (await res.json().catch(() => ({}))) as { detail?: string }
      if (!res.ok) {
        setError(payload.detail ?? "Could not create job.")
        return
      }
      setName("")
      setUrl("")
      router.refresh()
    } catch {
      setError("Unable to reach the control plane.")
    } finally {
      setPending(null)
    }
  }

  async function toggle(job: ScheduledJobRecord) {
    setPending(`toggle:${job.id}`)
    setError(null)
    try {
      const res = await fetch(`/api/proxy/jobs/${job.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: !job.enabled }),
      })
      if (!res.ok) {
        const p = (await res.json().catch(() => ({}))) as { detail?: string }
        setError(p.detail ?? "Update failed.")
        return
      }
      router.refresh()
    } catch {
      setError("Unable to reach the control plane.")
    } finally {
      setPending(null)
    }
  }

  async function remove(id: string) {
    setPending(`rm:${id}`)
    setError(null)
    try {
      const res = await fetch(`/api/proxy/jobs/${id}`, { method: "DELETE" })
      if (!res.ok) {
        const p = (await res.json().catch(() => ({}))) as { detail?: string }
        setError(p.detail ?? "Delete failed.")
        return
      }
      router.refresh()
    } catch {
      setError("Unable to reach the control plane.")
    } finally {
      setPending(null)
    }
  }

  async function toggleRuns(id: string) {
    const next = expandedId === id ? null : id
    setExpandedId(next)
    if (next && runs[id] === undefined) {
      try {
        const res = await fetch(`/api/proxy/jobs/${id}/runs`)
        const rows = res.ok ? ((await res.json()) as JobRunRecord[]) : []
        setRuns((r) => ({ ...r, [id]: Array.isArray(rows) ? rows : [] }))
      } catch {
        setRuns((r) => ({ ...r, [id]: [] }))
      }
    }
  }

  return (
    <div className="space-y-6">
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}

      <form
        onSubmit={create}
        className="flex flex-wrap items-end gap-3 rounded-2xl border border-border bg-muted p-4"
      >
        <label className="block text-sm">
          <span className="mb-2 block text-muted-foreground">Name</span>
          <input aria-label="Name" value={name} onChange={(e) => setName(e.target.value)} placeholder="nightly-ping" className={INPUT} required />
        </label>
        <label className="block text-sm">
          <span className="mb-2 block text-muted-foreground">Schedule (cron)</span>
          <input aria-label="Schedule" value={cron} onChange={(e) => setCron(e.target.value)} className={`${INPUT} w-40 font-mono`} required />
        </label>
        <label className="block text-sm">
          <span className="mb-2 block text-muted-foreground">Method</span>
          <select aria-label="Method" value={method} onChange={(e) => setMethod(e.target.value)} className={INPUT}>
            {["GET", "POST", "HEAD"].map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        </label>
        <label className="block flex-1 text-sm">
          <span className="mb-2 block text-muted-foreground">URL</span>
          <input aria-label="URL" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://your-app/cron" className={`${INPUT} w-full`} required />
        </label>
        <Button type="submit" icon={faPlus} disabled={pending !== null || !name || !url}>
          {pending === "create" ? "…" : "Add job"}
        </Button>
      </form>

      {jobs.length === 0 ? (
        <EmptyState
          title="No scheduled jobs"
          description="Schedule a recurring HTTP call — e.g. hit your app's /cron endpoint every 5 minutes."
        />
      ) : (
        <div className="space-y-3">
          {jobs.map((job) => {
            const expanded = expandedId === job.id
            const list = runs[job.id]
            return (
              <div key={job.id} className="overflow-hidden rounded-2xl border border-border bg-muted">
                <div className="flex flex-wrap items-center justify-between gap-3 p-4">
                  <button type="button" onClick={() => toggleRuns(job.id)} className="flex min-w-0 flex-1 flex-col items-start gap-1 text-left">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{job.name}</span>
                      <span className="rounded-full border border-border bg-background px-2 py-0.5 font-mono text-xs">{job.cron}</span>
                      <span className="text-xs text-muted-foreground">{job.method}</span>
                      {!job.enabled ? <span className="rounded-full bg-accent px-2 py-0.5 text-[11px] text-muted-foreground">paused</span> : null}
                    </div>
                    <span className="truncate font-mono text-xs text-muted-foreground">{job.url}</span>
                    {job.last_status ? (
                      <span className="text-xs text-muted-foreground">
                        last: <span className={cn("font-medium", STATUS_TONE[job.last_status])}>{job.last_status}</span>
                        {job.last_detail ? ` (${job.last_detail})` : ""} · {formatRelativeLabel(job.last_run_at)}
                      </span>
                    ) : <span className="text-xs text-muted-foreground">never run</span>}
                  </button>
                  <div className="flex items-center gap-2">
                    <Button size="sm" disabled={pending !== null} onClick={() => toggle(job)}>
                      {pending === `toggle:${job.id}` ? "…" : job.enabled ? "Pause" : "Resume"}
                    </Button>
                    <Button size="sm" icon={faTrash} disabled={pending !== null} onClick={() => remove(job.id)}>
                      {pending === `rm:${job.id}` ? "…" : "Delete"}
                    </Button>
                  </div>
                </div>

                {expanded ? (
                  <div className="border-t border-border px-4 pb-4 pt-3">
                    <div className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">Recent runs</div>
                    {list === undefined ? (
                      <p className="text-sm text-muted-foreground">Loading…</p>
                    ) : list.length === 0 ? (
                      <p className="text-sm text-muted-foreground">No runs yet.</p>
                    ) : (
                      <ul className="space-y-1">
                        {list.map((run, i) => (
                          <li key={`${run.started_at}-${i}`} className="flex items-center justify-between gap-3 rounded-lg border border-border bg-background px-3 py-1.5 text-xs">
                            <span className={cn("font-medium", STATUS_TONE[run.status])}>{run.status}</span>
                            <span className="font-mono text-muted-foreground">{run.detail}</span>
                            <span className="text-muted-foreground">{run.duration_ms}ms</span>
                            <span className="text-muted-foreground">{formatRelativeLabel(run.started_at)}</span>
                          </li>
                        ))}
                      </ul>
                    )}
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
