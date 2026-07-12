import { cn, normalizeStatus } from "@/lib/utils"

const toneStyles = {
  positive: "border-status-ok/25 bg-status-ok/10 text-status-ok",
  warning: "border-status-warn/25 bg-status-warn/10 text-status-warn",
  critical: "border-status-err/25 bg-status-err/10 text-status-err",
  info: "border-status-live/25 bg-status-live/10 text-status-live",
  neutral: "border-border bg-background text-muted-foreground",
} as const

const dotStyles = {
  positive: "bg-status-ok",
  warning: "bg-status-warn",
  critical: "bg-status-err",
  info: "bg-status-live",
  neutral: "bg-muted-foreground",
} as const

/**
 * App/deployment run state, made unmistakable: a colored dot (pulsing while
 * deploying) + a clear label (Running / Stopped / Deploying / …). Use this for
 * app status; {@link StatusBadge} stays for other domains (mail, tenants, DNS).
 */
export function AppStatus({ value, className }: { value: string; className?: string }) {
  const { label, tone, pulse } = normalizeStatus(value)
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium",
        toneStyles[tone],
        className,
      )}
    >
      <span className="relative flex size-1.5">
        {pulse ? (
          <span className={cn("absolute inline-flex h-full w-full animate-ping rounded-full opacity-75", dotStyles[tone])} />
        ) : null}
        <span className={cn("relative inline-flex size-1.5 rounded-full", dotStyles[tone])} />
      </span>
      {label}
    </span>
  )
}
