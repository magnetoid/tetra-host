import Link from "next/link"

import { cn } from "@/lib/utils"

export function PageHeader({
  eyebrow,
  title,
  description,
  action,
  className,
}: {
  eyebrow?: string
  title: string
  description?: string
  action?: React.ReactNode
  className?: string
}) {
  return (
    <section
      className={cn(
        "flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between",
        className,
      )}
    >
      <div>
        {eyebrow ? (
          <div className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
            {eyebrow}
          </div>
        ) : null}
        <h1 className="mt-2 font-display text-4xl font-semibold tracking-tight">{title}</h1>
        {description ? (
          <p className="mt-3 max-w-2xl text-muted-foreground">{description}</p>
        ) : null}
      </div>
      {action}
    </section>
  )
}

export function RefreshLink({
  href,
  label,
}: {
  href: string
  label: string
}) {
  return (
    <Link
      href={href}
      className="inline-flex items-center rounded-md border border-border px-4 py-2 text-sm font-medium shadow-sm transition-colors hover:bg-accent"
    >
      {label}
    </Link>
  )
}
