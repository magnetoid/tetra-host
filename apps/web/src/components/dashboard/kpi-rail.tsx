import { cn } from "@/lib/utils"

export type Kpi = {
  label: string
  value: string
  sub?: string
  tone?: "muted" | "ok" | "warn" | "err"
}

const TONE: Record<NonNullable<Kpi["tone"]>, string> = {
  muted: "text-muted-foreground",
  ok: "text-status-ok",
  warn: "text-status-warn",
  err: "text-status-err",
}

/**
 * Editorial KPI row — columns split by vertical hairlines (no cards), big mono
 * numerals, uppercase micro-labels. Matches the approved dashboard reference.
 */
export function KpiRail({ items }: { items: Kpi[] }) {
  return (
    <div className="grid grid-cols-2 divide-x divide-border border-y border-border sm:grid-cols-3 xl:grid-cols-6">
      {items.map((k) => (
        <div key={k.label} className="px-5 py-5">
          <div className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
            {k.label}
          </div>
          <div className="mt-1.5 font-mono text-[2rem] font-semibold leading-none tabular-nums">
            {k.value}
          </div>
          {k.sub ? <div className={cn("mt-2 text-xs", TONE[k.tone ?? "muted"])}>{k.sub}</div> : null}
        </div>
      ))}
    </div>
  )
}
