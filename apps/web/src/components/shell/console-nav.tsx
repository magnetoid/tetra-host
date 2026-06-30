"use client"

import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import Link from "next/link"
import { usePathname } from "next/navigation"

import { type NavItem, consoleNavItems } from "@/lib/navigation"
import { cn } from "@/lib/utils"

function SidebarLink({ item, active }: { item: NavItem; active: boolean }) {
  return (
    <Link
      href={item.href}
      className={cn(
        "flex items-center gap-3 rounded-lg px-3 py-2 text-zinc-300 transition hover:bg-zinc-800 hover:text-white",
        active && "bg-zinc-800 text-white",
      )}
    >
      {item.icon ? (
        <FontAwesomeIcon
          icon={item.icon}
          className={cn("h-4 w-4 shrink-0", active ? "text-primary" : "text-zinc-500")}
          fixedWidth
        />
      ) : null}
      {item.label}
    </Link>
  )
}

export function ConsoleNav({ adminRole }: { adminRole?: string }) {
  const pathname = usePathname()

  const visibleItems = consoleNavItems.filter(
    (item) => !item.platformAdminOnly || adminRole === "platform_admin",
  )

  return (
    <nav className="mt-8 space-y-1 text-sm">
      {visibleItems.map((item) => (
        <SidebarLink
          key={item.href}
          item={item}
          active={pathname === item.href || pathname.startsWith(`${item.href}/`)}
        />
      ))}
    </nav>
  )
}
