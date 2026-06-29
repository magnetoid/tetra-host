import type { HTMLAttributes } from "react"

import { cn } from "@/lib/utils"

/** The one surface panel — consistent radius, border, muted bg, and padding. */
export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-2xl border border-border bg-muted p-6", className)} {...props} />
}

/** Optional standard card header: a title (left) and optional right-aligned slot. */
export function CardHeader({
  title,
  action,
}: {
  title: string
  action?: React.ReactNode
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <h2 className="text-lg font-semibold">{title}</h2>
      {action ? <div className="text-sm text-zinc-500">{action}</div> : null}
    </div>
  )
}
