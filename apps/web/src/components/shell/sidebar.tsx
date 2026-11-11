"use client"

import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import Link from "next/link"
import { usePathname } from "next/navigation"

import { TetraWordmark } from "@/components/brand/tetra-wordmark"
import { useScopeLabels } from "@/components/shell/scope-labels"
import { faChevronLeft, faTableColumns } from "@/lib/icons"
import { isActive, resolveScope, sidebarFor } from "@/lib/navigation"
import { cn } from "@/lib/utils"

const SCOPE_CAPTION = { platform: "Super admin", team: "Team", app: "App" } as const

/** The menu of the current scope. Shared by the desktop sidebar and the mobile drawer. */
export function SidebarNav({
  isPlatformAdmin,
  collapsed = false,
  onNavigate,
}: {
  isPlatformAdmin: boolean
  collapsed?: boolean
  onNavigate?: () => void
}) {
  const pathname = usePathname()
  const labels = useScopeLabels()
  const scope = resolveScope(pathname, isPlatformAdmin)
  const model = sidebarFor(scope, isPlatformAdmin)
  const title =
    scope.kind === "platform"
      ? "Platform"
      : scope.kind === "team"
        ? labels.team || "Team"
        : labels.app || scope.app

  return (
    <div className="flex flex-col gap-0.5">
      {model.back ? (
        <Link
          href={model.back.href}
          onClick={onNavigate}
          title={collapsed ? model.back.label : undefined}
          className={cn(
            "flex h-8 items-center gap-2.5 rounded-md px-2.5 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground",
            collapsed && "justify-center px-0",
          )}
        >
          <FontAwesomeIcon icon={faChevronLeft} className="size-3" />
          {collapsed ? <span className="sr-only">Back to {model.back.label}</span> : <span className="truncate">{model.back.label}</span>}
        </Link>
      ) : null}

      {collapsed ? null : (
        <div className="mb-2 mt-1 px-2.5 py-1.5">
          <div className="truncate text-sm font-semibold">{title}</div>
          <div className="text-xs text-muted-foreground">{SCOPE_CAPTION[scope.kind]}</div>
        </div>
      )}

      <nav aria-label={`${SCOPE_CAPTION[scope.kind]} menu`} className="flex flex-col gap-px">
        {model.sections.map((section, index) => (
          <div key={section.title ?? index} className="flex flex-col gap-px">
            {section.title && !collapsed ? (
              <div className="px-2.5 pb-1 pt-4 text-xs font-medium text-muted-foreground">{section.title}</div>
            ) : null}
            {section.title && collapsed ? <div className="mx-2 my-2 border-t border-border" /> : null}
            {section.items
              .filter((item) => !item.platformAdminOnly || isPlatformAdmin)
              .map((item) => {
                const active = isActive(item, pathname)
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={onNavigate}
                    aria-current={active ? "page" : undefined}
                    title={collapsed ? item.label : undefined}
                    className={cn(
                      "flex h-8 items-center gap-2.5 rounded-md px-2.5 text-sm transition-colors",
                      active
                        ? "bg-selected font-medium text-foreground"
                        : "text-muted-foreground hover:bg-accent hover:text-foreground",
                      collapsed && "justify-center px-0",
                    )}
                  >
                    {item.icon ? <FontAwesomeIcon icon={item.icon} className="size-3.5 shrink-0" /> : null}
                    {collapsed ? <span className="sr-only">{item.label}</span> : <span className="truncate">{item.label}</span>}
                  </Link>
                )
              })}
          </div>
        ))}
      </nav>
    </div>
  )
}

/** Desktop left sidebar (lg+). Collapses to an icon rail; the choice is kept in a cookie. */
export function Sidebar({
  isPlatformAdmin,
  collapsed,
  onToggle,
}: {
  isPlatformAdmin: boolean
  collapsed: boolean
  onToggle: () => void
}) {
  return (
    <aside
      className={cn(
        "sticky top-0 hidden h-screen shrink-0 flex-col border-r border-border bg-sidebar px-2.5 py-3 lg:flex",
        collapsed ? "w-16" : "w-60",
      )}
    >
      <Link
        href={isPlatformAdmin ? "/super-admin" : "/dashboard"}
        className={cn("mb-3 flex h-9 items-center px-2.5", collapsed && "justify-center px-0")}
      >
        <TetraWordmark compact={collapsed} />
      </Link>
      <div className="min-h-0 flex-1 overflow-y-auto">
        <SidebarNav isPlatformAdmin={isPlatformAdmin} collapsed={collapsed} />
      </div>
      <button
        type="button"
        onClick={onToggle}
        className={cn(
          "mt-2 flex h-8 items-center gap-2.5 rounded-md px-2.5 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground",
          collapsed && "justify-center px-0",
        )}
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        <FontAwesomeIcon icon={faTableColumns} className="size-3.5" />
        {collapsed ? null : <span>Collapse</span>}
      </button>
    </aside>
  )
}
