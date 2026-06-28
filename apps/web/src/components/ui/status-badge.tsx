import { cn, statusTone } from "@/lib/utils"

const toneStyles = {
  positive: "border-emerald-900 bg-emerald-950 text-emerald-300",
  warning: "border-amber-900 bg-amber-950 text-amber-200",
  critical: "border-red-900 bg-red-950 text-red-200",
  neutral: "border-border bg-background text-zinc-400",
} as const

export function StatusBadge({
  value,
  className,
}: {
  value: string
  className?: string
}) {
  const tone = statusTone(value)

  return (
    <span
      className={cn(
        "inline-flex rounded-full border px-3 py-1 text-xs font-medium",
        toneStyles[tone],
        className,
      )}
    >
      {value}
    </span>
  )
}
