"use client"

import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import Link from "next/link"
import { usePathname } from "next/navigation"

import { projectNavItems } from "@/lib/navigation"
import { cn } from "@/lib/utils"

/**
 * Mobile/tablet project menu (`lg:hidden`). On desktop the main sidebar slides
 * to the project menu instead (see ConsoleNav); both share `projectNavItems`.
 */
export function ProjectSubNav({
  projectId,
  projectName,
}: {
  projectId: string
  projectName: string
}) {
  const pathname = usePathname()
  const items = projectNavItems(projectId)

  return (
    <aside className="rounded-2xl border border-border bg-muted/40 p-3">
      <div className="mb-2 flex items-center gap-3 px-1">
        <Link
          href="/projects"
          className="text-xs text-zinc-400 transition hover:text-white"
          aria-label="Back to projects"
        >
          ← Projects
        </Link>
        <span className="text-zinc-600">/</span>
        <h2 className="truncate text-sm font-semibold text-zinc-100">{projectName}</h2>
      </div>

      <nav className="flex gap-1 overflow-x-auto pb-1">
        {items.map((item) => {
          const active = item.exact ? pathname === item.href : pathname.startsWith(item.href)
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-zinc-300 transition hover:bg-zinc-800 hover:text-white",
                active && "bg-zinc-800 text-white",
              )}
            >
              <FontAwesomeIcon
                icon={item.icon}
                className={cn("h-4 w-4 shrink-0", active ? "text-primary" : "text-zinc-500")}
                fixedWidth
              />
              {item.label}
            </Link>
          )
        })}
      </nav>
    </aside>
  )
}
