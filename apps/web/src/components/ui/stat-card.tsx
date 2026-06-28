import type { LucideIcon } from "lucide-react"

import { cn } from "@/lib/utils"

export function StatCard({
  icon: Icon,
  label,
  value,
  hint,
  accent = "text-primary",
}: {
  icon: LucideIcon
  label: string
  value: string | number
  hint?: string
  accent?: string
}) {
  return (
    <div className="rounded-2xl border border-border bg-zinc-950/70 p-5 shadow-sm">
      <div className="flex items-center gap-2 text-sm text-zinc-500">
        <span className={cn("grid h-7 w-7 place-items-center rounded-lg bg-background", accent)}>
          <Icon className="h-4 w-4" />
        </span>
        {label}
      </div>
      <div className="mt-3 text-3xl font-semibold tracking-tight">{value}</div>
      {hint ? <div className="mt-1 text-xs text-zinc-500">{hint}</div> : null}
    </div>
  )
}
