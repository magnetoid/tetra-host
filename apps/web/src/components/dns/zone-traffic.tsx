"use client"

import { AreaChart, type AreaPoint } from "@/components/charts/area-chart"
import type { ZoneAnalytics } from "@/lib/types"
import { formatBytes, formatCompactNumber } from "@/lib/utils"

const SERIES = [
  { key: "requests", label: "Requests", color: "#7c3aed" },
  { key: "cached_requests", label: "Cached", color: "#34d399" },
]

/** Traffic summary chips + a requests/cached area chart for one zone. */
export function ZoneTraffic({ analytics }: { analytics: ZoneAnalytics }) {
  const totals = analytics.totals
  const data: AreaPoint[] = analytics.points.map((point) => ({
    date: point.date,
    requests: point.requests,
    cached_requests: point.cached_requests,
  }))

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Requests" value={formatCompactNumber(totals.requests)} />
        <Stat label="Cached" value={formatCompactNumber(totals.cached_requests)} />
        <Stat label="Bandwidth" value={formatBytes(totals.bytes)} />
        <Stat
          label="Threats"
          value={formatCompactNumber(totals.threats)}
          accent={totals.threats > 0 ? "text-red-400" : undefined}
        />
      </div>
      <AreaChart data={data} series={SERIES} valueFormatter={formatCompactNumber} />
    </div>
  )
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="rounded-xl border border-border bg-background p-3">
      <div className="text-xs text-zinc-500">{label}</div>
      <div className={`mt-1 text-lg font-semibold tabular-nums ${accent ?? ""}`}>{value}</div>
    </div>
  )
}
