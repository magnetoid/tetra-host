"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"

import { consoleNavItems } from "@/lib/navigation"
import { cn } from "@/lib/utils"

function SidebarLink({
  href,
  label,
  active,
}: {
  href: string
  label: string
  active: boolean
}) {
  return (
    <Link
      href={href}
      className={cn(
        "block rounded-lg px-3 py-2 text-zinc-300 transition hover:bg-zinc-800 hover:text-white",
        active && "bg-zinc-800 text-white",
      )}
    >
      {label}
    </Link>
  )
}

export function ConsoleNav() {
  const pathname = usePathname()

  return (
    <nav className="mt-8 space-y-1 text-sm">
      {consoleNavItems.map((item) => (
        <SidebarLink
          key={item.href}
          href={item.href}
          label={item.label}
          active={pathname === item.href || pathname.startsWith(`${item.href}/`)}
        />
      ))}
    </nav>
  )
}
