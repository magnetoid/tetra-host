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
    <div className="rounded-2xl border border-border bg-zinc-950/70 p-5 shadow-sm">
      <div className="flex items-center gap-2 text-sm text-zinc-500">
        <span className={cn("grid h-7 w-7 place-items-center rounded-lg bg-background", accent)}>
          <FontAwesomeIcon icon={icon} className="h-4 w-4" />
        </span>
        {label}
      </div>
      <div className="mt-3 text-3xl font-semibold tracking-tight">{value}</div>
      {hint ? <div className="mt-1 text-xs text-zinc-500">{hint}</div> : null}
    </div>
  )
}
