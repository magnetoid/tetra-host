import type { HTMLAttributes } from "react"
import { cva } from "class-variance-authority"

import { cn } from "@/lib/utils"

const cardVariants = cva(
  "rounded-lg border border-border bg-card text-card-foreground p-6 shadow-sm",
)

/** The one surface panel — New York radius, hairline border, card bg, padding. */
export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn(cardVariants(), className)} {...props} />
}

/**
 * Standard card header: a title (left) and optional right-aligned slot. Kept as
 * the project's established API (title/action props) — most surfaces use this.
 */
export function CardHeader({
  title,
  action,
  className,
}: {
  title: string
  action?: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn("flex items-center justify-between gap-3", className)}>
      <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
      {action ? <div className="text-sm text-muted-foreground">{action}</div> : null}
    </div>
  )
}

/** Canonical shadcn sub-parts, for richer composition in new surfaces. */
export function CardTitle({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={cn("text-lg font-semibold leading-none tracking-tight", className)} {...props} />
}

export function CardDescription({ className, ...props }: HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn("text-sm text-muted-foreground", className)} {...props} />
}

export function CardContent({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn(className)} {...props} />
}

export function CardFooter({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex items-center gap-2", className)} {...props} />
}

export { cardVariants }
