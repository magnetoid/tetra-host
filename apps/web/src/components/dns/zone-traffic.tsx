"use client"

// Client component: it passes formatter functions to the (client) AreaChart, which
// can't cross a server→client prop boundary. It has no server-only needs.
import { AreaChart } from "@/components/tremor/area-chart"
import type { ZoneAnalytics } from "@/lib/types"
import { formatBytes, formatCompactNumber } from "@/lib/utils"

const CATEGORIES = ["requests", "cached_requests"]
const CATEGORY_LABELS = { requests: "Requests", cached_requests: "Cached" }
// Violet for total requests, emerald for the cached subset.
const COLORS = ["var(--chart-1)", "var(--chart-3)"]

/** Traffic summary chips + a requests/cached area chart for one zone. */
export function ZoneTraffic({ analytics }: { analytics: ZoneAnalytics }) {
  const totals = analytics.totals
  const data = analytics.points.map((point) => ({
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
          accent={totals.threats > 0 ? "text-status-err" : undefined}
        />
      </div>
      <AreaChart
        data={data}
        index="date"
        categories={CATEGORIES}
        categoryLabels={CATEGORY_LABELS}
        colors={COLORS}
        valueFormatter={formatCompactNumber}
        xValueFormatter={(value) => value.slice(5)}
        emptyMessage="No traffic data for this window."
      />
    </div>
  )
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="rounded-xl border border-border bg-background p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={`mt-1 font-mono text-lg font-semibold tabular-nums ${accent ?? ""}`}>
        {value}
      </div>
    </div>
  )
}
