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
 * The console sidebar nav. Outside a project it shows the global menu; inside a
 * project (`/projects/<id>/…`) the whole menu slides left to reveal that
 * project's menu (with a "← Projects" back link), Vercel-style. Both panels are
 * always mounted so the swap animates; the off-screen panel is `inert`.
 */
export function ConsoleNav({
  adminRole,
  projects = [],
}: {
  adminRole?: string
  projects?: ProjectMeta[]
}) {
  const pathname = usePathname()

  // Project context = /projects/<id> or /projects/<id>/… — but NOT the list at /projects.
  const match = /^\/projects\/([^/]+)(?:\/|$)/.exec(pathname)
  const activeProjectId = match?.[1]
  const inProject = Boolean(activeProjectId)

  const visibleItems = consoleNavItems.filter(
    (item) => !item.platformAdminOnly || adminRole === "platform_admin",
  )

  const projectName = activeProjectId
    ? (projects.find((p) => p.id === activeProjectId)?.name ?? "Project")
    : ""
  const projectItems = activeProjectId ? projectNavItems(activeProjectId) : []

  return (
    <div className="mt-8 overflow-hidden">
      <div
        className="flex w-[200%] transition-transform duration-300 ease-out motion-reduce:transition-none"
        style={{ transform: inProject ? "translateX(-50%)" : "translateX(0)" }}
      >
        {/* Panel A — global menu */}
        <nav className="w-1/2 shrink-0 space-y-1 pr-px text-sm" inert={inProject || undefined}>
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

        {/* Panel B — project menu */}
        <div className="w-1/2 shrink-0 pl-px text-sm" inert={!inProject || undefined}>
          <Link
            href="/projects"
            className="mb-2 flex items-center gap-2 rounded-lg px-3 py-2 text-muted-foreground transition hover:bg-accent hover:text-foreground"
          >
            <span aria-hidden>←</span> Projects
          </Link>
          <div className="mb-2 px-3">
            <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Project
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
      </div>
    </div>
  )
}
