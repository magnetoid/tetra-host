import { cn } from "@/lib/utils"

export function MetricCard({
  label,
  value,
  hint,
  className,
}: {
  label: string
  value: string | number
  hint?: string
  className?: string
}) {
  return (
    <div className={cn("rounded-lg border border-border bg-card p-5 shadow-sm", className)}>
      <div className="text-sm text-muted-foreground">{label}</div>
      <div className="mt-2 font-mono text-3xl font-semibold tracking-tight tabular-nums">{value}</div>
      {hint ? <div className="mt-2 text-xs text-muted-foreground">{hint}</div> : null}
    </div>
  )
}
