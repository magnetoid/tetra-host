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
        {eyebrow ? <div className="text-sm text-zinc-500">{eyebrow}</div> : null}
        <h1 className="mt-2 text-4xl font-semibold tracking-tight">{title}</h1>
        {description ? (
          <p className="mt-3 max-w-2xl text-zinc-400">{description}</p>
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
      className="inline-flex rounded-lg bg-white px-4 py-2 text-sm font-medium text-black transition hover:bg-zinc-200"
    >
      {label}
    </Link>
  )
}
