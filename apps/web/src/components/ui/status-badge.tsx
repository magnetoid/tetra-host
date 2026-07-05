import { cn, statusTone } from "@/lib/utils"

const toneStyles = {
  positive: "border-status-ok/25 bg-status-ok/10 text-status-ok",
  warning: "border-status-warn/25 bg-status-warn/10 text-status-warn",
  critical: "border-status-err/25 bg-status-err/10 text-status-err",
  neutral: "border-border bg-background text-muted-foreground",
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
