"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"

import { consoleNavItems } from "@/lib/navigation"
import { cn } from "@/lib/utils"

/**
 * Primary console navigation as an underline top-tab row (editorial redesign —
 * replaces the left sidebar). Horizontally scrollable so the full destination
 * set is preserved without wrapping; the long tail is also reachable via ⌘K.
 */
export function TopTabs({ adminRole }: { adminRole?: string }) {
  const pathname = usePathname()
  const items = consoleNavItems.filter(
    (item) => !item.platformAdminOnly || adminRole === "platform_admin",
  )

  return (
    <nav
      aria-label="Primary"
      className="flex items-stretch gap-1 overflow-x-auto border-b border-border px-4 lg:px-6 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
    >
      {items.map((item) => {
        const active =
          item.href === "/dashboard"
            ? pathname === "/dashboard"
            : pathname === item.href || pathname.startsWith(`${item.href}/`)
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "relative whitespace-nowrap px-3 py-3 text-sm transition-colors",
              active
                ? "font-medium text-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {item.label}
            <span
              className={cn(
                "absolute inset-x-3 -bottom-px h-0.5 rounded-full transition-colors",
                active ? "bg-foreground" : "bg-transparent",
              )}
            />
          </Link>
        )
      })}
    </nav>
  )
}
