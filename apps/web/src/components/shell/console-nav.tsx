"use client"

import type { IconDefinition } from "@fortawesome/fontawesome-svg-core"
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import Link from "next/link"
import { usePathname } from "next/navigation"

import { consoleNavItems, projectNavItems } from "@/lib/navigation"
import { cn } from "@/lib/utils"

type ProjectMeta = { id: string; name: string }

function NavRow({
  href,
  label,
  icon,
  active,
}: {
  href: string
  label: string
  icon?: IconDefinition
  active: boolean
}) {
  return (
    <Link
      href={href}
      className={cn(
        "flex items-center gap-3 rounded-lg px-3 py-2 text-muted-foreground transition hover:bg-accent hover:text-foreground",
        active && "bg-accent font-medium text-foreground",
      )}
    >
      {icon ? (
        <FontAwesomeIcon
          icon={icon}
          className={cn("h-4 w-4 shrink-0", active ? "text-primary" : "text-muted-foreground")}
          fixedWidth
        />
      ) : null}
      {label}
    </Link>
  )
}

/**
 * The console sidebar nav. Strictly context-scoped: inside a project
 * (`/projects/<id>/…`) it renders ONLY that project's menu (+ a back link and a
 * tenant › project header) — the global menu is not mounted, so nothing spills
 * over. Everywhere else it renders the global menu.
 */
export function ConsoleNav({
  adminRole,
  tenantName,
  projects = [],
}: {
  adminRole?: string
  tenantName?: string
  projects?: ProjectMeta[]
}) {
  const pathname = usePathname()

  // Project context = /projects/<id> or /projects/<id>/… — but NOT the list at /projects.
  const match = /^\/projects\/([^/]+)(?:\/|$)/.exec(pathname)
  const activeProjectId = match?.[1]

  // ── Inside a project: ONLY the project menu ──────────────────────────────
  if (activeProjectId) {
    const projectName = projects.find((p) => p.id === activeProjectId)?.name ?? "Project"
    const projectItems = projectNavItems(activeProjectId)
    return (
      <div className="mt-8 text-sm">
        <Link
          href="/projects"
          className="mb-3 flex items-center gap-2 rounded-lg px-3 py-2 text-muted-foreground transition hover:bg-accent hover:text-foreground"
        >
          <span aria-hidden>←</span> All projects
        </Link>
        <div className="mb-3 px-3">
          <p className="truncate text-xs font-medium uppercase tracking-wider text-muted-foreground">
            {tenantName ? `${tenantName} ›` : "Project"}
          </p>
          <h2 className="mt-1 truncate text-sm font-semibold text-foreground">{projectName}</h2>
        </div>
        <nav className="space-y-1">
          {projectItems.map((item) => (
            <NavRow
              key={item.href}
              href={item.href}
              label={item.label}
              icon={item.icon}
              active={item.exact ? pathname === item.href : pathname.startsWith(item.href)}
            />
          ))}
        </nav>
      </div>
    )
  }

  // ── Everywhere else: the global menu ─────────────────────────────────────
  const visibleItems = consoleNavItems.filter(
    (item) => !item.platformAdminOnly || adminRole === "platform_admin",
  )
  return (
    <nav className="mt-8 space-y-1 text-sm">
      {visibleItems.map((item) => (
        <NavRow
          key={item.href}
          href={item.href}
          label={item.label}
          icon={item.icon}
          active={pathname === item.href || pathname.startsWith(`${item.href}/`)}
        />
      ))}
    </nav>
  )
}
