import { cn } from "@/lib/utils"

// Theme-aware tones built on the semantic status tokens (readable in light + dark).
const toneStyles = {
  error: "border-status-err/30 bg-status-err/10 text-status-err",
  success: "border-status-ok/30 bg-status-ok/10 text-status-ok",
  info: "border-border bg-muted text-muted-foreground",
} as const

export function AlertBanner({
  tone = "info",
  children,
  className,
}: {
  tone?: keyof typeof toneStyles
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn("rounded-2xl border p-4 text-sm", toneStyles[tone], className)}>
      {children}
    </div>
  )
}
