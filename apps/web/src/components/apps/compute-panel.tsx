"use client"

import { useEffect, useState } from "react"

import { BarList } from "@/components/tremor/bar-list"
import { AlertBanner } from "@/components/ui/alert-banner"
import { Card, CardHeader } from "@/components/ui/card"
import { EmptyState } from "@/components/ui/empty-state"
import { StatCard } from "@/components/ui/stat-card"
import { faGaugeHigh, faLayerGroup, faServer } from "@/lib/icons"
import type { ComputeMetrics } from "@/lib/types"

const POLL_MS = 4000

export function ComputePanel({
  project,
  initial,
}: {
  project: string
  initial: ComputeMetrics | null
}) {
  const [metrics, setMetrics] = useState<ComputeMetrics | null>(initial)
  const [error, setError] = useState<string | null>(null)
  const [live, setLive] = useState(true)

  useEffect(() => {
    let cancelled = false
    const tick = () => {
      fetch(`/api/proxy/apps/${project}/compute`)
        .then(async (res) => {
          if (cancelled) return
          if (!res.ok) {
            const payload = (await res.json().catch(() => ({}))) as { detail?: string }
            setError(payload.detail ?? "Unable to load compute stats.")
            return
          }
          setError(null)
          setMetrics((await res.json()) as ComputeMetrics)
        })
        .catch(() => {
          if (!cancelled) setError("Unable to reach the control plane.")
        })
    }
    tick()
    if (!live) return () => {
      cancelled = true
    }
    const timer = setInterval(tick, POLL_MS)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [project, live])

  const samples = metrics?.samples ?? []

  return (
    <div className="space-y-6">
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}

      <div className="flex items-center justify-between">
        <div className="text-sm text-muted-foreground">Live per-container CPU, memory &amp; network</div>
        <button
          type="button"
          onClick={() => setLive((v) => !v)}
          className="rounded-lg border border-border px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
        >
          {live ? (
            <span className="flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-status-ok" />
              Live
            </span>
          ) : (
            "Paused"
          )}
        </button>
      </div>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatCard
          icon={faGaugeHigh}
          label="CPU"
          value={`${metrics?.cpu_percent ?? 0}%`}
          accent="text-primary"
          hint="summed across containers"
        />
        <StatCard
          icon={faServer}
          label="Memory"
          value={`${metrics?.mem_used_mb ?? 0} MB`}
          accent="text-status-live"
          hint="resident set size"
        />
        <StatCard icon={faLayerGroup} label="Containers" value={samples.length} accent="text-status-ok" />
      </section>

      {samples.length === 0 ? (
        <EmptyState
          title="No running containers"
          description="Deploy or start this app to see live compute metrics."
        />
      ) : (
        <section className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader title="CPU by container" action="%" />
            <div className="mt-4">
              <BarList
                data={samples.map((s) => ({ name: s.name, value: s.cpu_percent }))}
                valueFormatter={(v) => `${v}%`}
              />
            </div>
          </Card>
          <Card>
            <CardHeader title="Memory by container" action="MB" />
            <div className="mt-4">
              <BarList
                data={samples.map((s) => ({ name: s.name, value: s.mem_used_mb }))}
                valueFormatter={(v) => `${v} MB`}
              />
            </div>
          </Card>
        </section>
      )}
    </div>
  )
}
