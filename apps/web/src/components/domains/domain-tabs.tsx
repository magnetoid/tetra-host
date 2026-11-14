"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"

import { DOMAIN_TABS, domainHref } from "@/lib/domains"
import { cn } from "@/lib/utils"

/** DNS / Web / Mail tabs of one domain, with a count next to each. */
export function DomainTabs({
  name,
  counts,
}: {
  name: string
  counts: Partial<Record<"dns" | "web" | "mail", number | string>>
}) {
  const pathname = usePathname()
  return (
    <div className="flex flex-wrap items-center gap-1 border-b border-border" role="tablist" aria-label="Domain">
      {DOMAIN_TABS.map((tab) => {
        const href = domainHref(name, tab.key)
        const active = pathname === href || pathname.startsWith(`${href}/`)
        return (
          <Link
            key={tab.key}
            href={href}
            role="tab"
            aria-selected={active}
            className={cn(
              "-mb-px border-b-2 px-3 py-2 text-sm transition-colors",
              active
                ? "border-primary font-medium text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {tab.label}
            {counts[tab.key] !== undefined ? (
              <span className="ml-1.5 text-xs text-muted-foreground">{counts[tab.key]}</span>
            ) : null}
          </Link>
        )
      })}
    </div>
  )
}
