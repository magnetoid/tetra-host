import { cn } from "@/lib/utils"

const toneStyles = {
  error: "border-red-900 bg-red-950/70 text-red-100",
  success: "border-emerald-900 bg-emerald-950/70 text-emerald-200",
  info: "border-border bg-muted text-zinc-300",
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
