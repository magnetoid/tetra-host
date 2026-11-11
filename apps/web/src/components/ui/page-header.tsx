import Link from "next/link"

import { cn } from "@/lib/utils"

export function PageHeader({
  eyebrow,
  title,
  description,
  action,
  className,
  as: Heading = "h1",
}: {
  eyebrow?: string
  title: string
  description?: string
  action?: React.ReactNode
  className?: string
  /** `h2` inside layouts that already render the page's h1 (app tabs). */
  as?: "h1" | "h2"
}) {
  return (
    <section
      className={cn(
        "flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between",
        className,
      )}
    >
      <div>
        {eyebrow ? (
          <div className="mb-1 text-xs font-medium text-muted-foreground">{eyebrow}</div>
        ) : null}
        <Heading
          className={cn(
            "font-semibold tracking-tight",
            Heading === "h1" ? "text-xl" : "text-base",
          )}
        >
          {title}
        </Heading>
        {description ? (
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">{description}</p>
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
      className="inline-flex h-8 items-center rounded-md border border-border px-3 text-sm font-medium transition-colors hover:bg-accent"
    >
      {label}
    </Link>
  )
}
