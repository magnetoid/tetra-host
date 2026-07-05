import type { IconDefinition } from "@fortawesome/fontawesome-svg-core"
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"

import { cn } from "@/lib/utils"

export function StatCard({
  icon,
  label,
  value,
  hint,
  accent = "text-primary",
}: {
  icon: IconDefinition
  label: string
  value: string | number
  hint?: string
  accent?: string
}) {
  return (
    <div className="rounded-2xl border border-border bg-card p-5 shadow-sm transition-colors hover:border-primary/30">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <span className={cn("grid size-7 place-items-center rounded-lg bg-background", accent)}>
          <FontAwesomeIcon icon={icon} className="h-4 w-4" />
        </span>
        {label}
      </div>
      <div className="mt-3 font-mono text-3xl font-semibold tracking-tight tabular-nums">{value}</div>
      {hint ? <div className="mt-1 text-xs text-muted-foreground">{hint}</div> : null}
    </div>
  )
}
