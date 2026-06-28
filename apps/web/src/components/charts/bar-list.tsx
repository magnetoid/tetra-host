import { cn } from "@/lib/utils"

export type Bar = { name: string; value: number; color?: string }

/** Tremor-style horizontal bar list (pure CSS — no chart engine needed). */
export function BarList({
  data,
  valueFormatter,
}: {
  data: Bar[]
  valueFormatter?: (value: number) => string
}) {
  const max = Math.max(1, ...data.map((bar) => bar.value))
  return (
    <div className="space-y-2">
      {data.map((bar) => (
        <div key={bar.name} className="flex items-center gap-3">
          <div className="relative h-9 flex-1 overflow-hidden rounded-md bg-background">
            <div
              className={cn("absolute inset-y-0 left-0 rounded-md transition-all", bar.color ?? "bg-primary/40")}
              style={{ width: `${Math.max(3, (bar.value / max) * 100)}%` }}
            />
            <div className="relative flex h-full items-center px-3 text-sm text-zinc-200">{bar.name}</div>
          </div>
          <div className="w-12 text-right text-sm tabular-nums text-zinc-300">
            {valueFormatter ? valueFormatter(bar.value) : bar.value}
          </div>
        </div>
      ))}
    </div>
  )
}
