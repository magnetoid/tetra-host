"use client"

import type { IconDefinition } from "@fortawesome/fontawesome-svg-core"
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import Link from "next/link"
import { usePathname } from "next/navigation"

import { consoleNavItems, NAV_SECTIONS, projectNavItems } from "@/lib/navigation"
import { activeGroup, type ProjectGroup } from "@/lib/projects"
import { cn } from "@/lib/utils"

type ProjectMeta = ProjectGroup

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
 * The console sidebar nav. Strictly context-scoped: inside an app
 * (`/projects/<project>/apps/<app>/…`) it renders ONLY that app's menu (+ a
 * back link and a tenant › project › app header) — the global menu is not
 * mounted, so nothing spills over. Everywhere else it renders the global menu.
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

  // App context = /projects/<project>/apps/<app>[/…]. The project detail page
  // (/projects/<project>) and the list (/projects) keep the global menu.
  const match = /^\/projects\/([^/]+)\/apps\/([^/]+)(?:\/|$)/.exec(pathname)
  const activeProjectSlug = match?.[1]
  const activeAppId = match?.[2]

  // ── Inside an app: ONLY the app menu ─────────────────────────────────────
  if (activeProjectSlug && activeAppId) {
    const group = activeGroup(projects, activeProjectSlug)
    const projectName = group?.name ?? "Project"
    const appName = group?.apps.find((a) => a.id === activeAppId)?.name ?? "App"
    const projectItems = projectNavItems(activeProjectSlug, activeAppId)
    return (
      <div className="mt-8 text-sm">
        <Link
          href={`/projects/${activeProjectSlug}`}
          className="mb-3 flex items-center gap-2 rounded-lg px-3 py-2 text-muted-foreground transition hover:bg-accent hover:text-foreground"
        >
          <span aria-hidden>←</span> {projectName}
        </Link>
        <div className="mb-3 px-3">
          <p className="truncate text-xs font-medium uppercase tracking-wider text-muted-foreground">
            {tenantName ? `${tenantName} › ${projectName}` : projectName}
          </p>
          <h2 className="mt-1 truncate text-sm font-semibold text-foreground">{appName}</h2>
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

  // ── Everywhere else: the global menu, grouped into sections ──────────────
  const visibleItems = consoleNavItems.filter(
    (item) => !item.platformAdminOnly || adminRole === "platform_admin",
  )
  return (
    <nav className="mt-8 space-y-6 text-sm">
      {NAV_SECTIONS.map((section) => {
        const items = visibleItems.filter((item) => item.section === section)
        if (items.length === 0) return null
        return (
          <div key={section} className="space-y-1">
            <div className="px-3 pb-1 font-mono text-[10px] uppercase tracking-wider text-muted-foreground/70">
              {section}
            </div>
            {items.map((item) => (
              <NavRow
                key={item.href}
                href={item.href}
                label={item.label}
                icon={item.icon}
                active={pathname === item.href || pathname.startsWith(`${item.href}/`)}
              />
            ))}
          </div>
        )
      })}
    </nav>
  )
}
