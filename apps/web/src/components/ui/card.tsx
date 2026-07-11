import type { HTMLAttributes } from "react"
import { cva } from "class-variance-authority"

import { cn } from "@/lib/utils"

const cardVariants = cva("rounded-2xl border border-border bg-card p-6 shadow-sm")

/** The one surface panel — consistent radius, hairline border, card bg, and padding. */
export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn(cardVariants(), className)} {...props} />
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
      {action ? <div className="text-sm text-muted-foreground">{action}</div> : null}
    </div>
  )
}

export { cardVariants }
