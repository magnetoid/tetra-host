"use client"

import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import Link from "next/link"
import { usePathname } from "next/navigation"

import { TetraWordmark } from "@/components/brand/tetra-wordmark"
import { Collapsible } from "@/components/shell/collapsible"
import { ProjectTree } from "@/components/shell/project-tree"
import { useScopeLabels } from "@/components/shell/scope-labels"
import { faChevronLeft, faChevronRight, faTableColumns } from "@/lib/icons"
import { useNavOpen } from "@/lib/nav-state"
import { isActive, resolveScope, sidebarFor, type NavItem, type NavSection } from "@/lib/navigation"
import { cn } from "@/lib/utils"

const SCOPE_CAPTION = {
  platform: "Super admin",
  team: "Team",
  project: "Team",
  app: "App",
  database: "Database",
} as const

/** The menu of the current scope. Shared by the desktop sidebar and the mobile drawer. */
export function SidebarNav({
  isPlatformAdmin,
  team = "",
  collapsed = false,
  onNavigate,
}: {
  isPlatformAdmin: boolean
  /** The signed-in team's `/teams/{team}` segment; enables the project tree. */
  team?: string
  collapsed?: boolean
  onNavigate?: () => void
}) {
  const pathname = usePathname()
  const labels = useScopeLabels()
  const scope = resolveScope(pathname, isPlatformAdmin)
  const model = sidebarFor(scope, isPlatformAdmin, labels)
  const title =
    scope.kind === "platform"
      ? "Platform"
      : scope.kind === "team" || scope.kind === "project"
        ? labels.team || "Team"
        : scope.kind === "app"
          ? labels.app || scope.app
          : labels.app || "Database"

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
          <SidebarSection
            key={section.title ?? index}
            section={section}
            isPlatformAdmin={isPlatformAdmin}
            pathname={pathname}
            collapsed={collapsed}
            team={team}
            onNavigate={onNavigate}
          />
        ))}
      </nav>
    </div>
  )
}

/** A titled group of the menu that slides open and shut; untitled groups always show. */
function SidebarSection({
  section,
  isPlatformAdmin,
  pathname,
  collapsed,
  team,
  onNavigate,
}: {
  section: NavSection
  isPlatformAdmin: boolean
  pathname: string
  collapsed: boolean
  team: string
  onNavigate?: () => void
}) {
  const [open, toggle] = useNavOpen(`section:${section.title ?? ""}`, true)
  const items = section.items.filter((item) => !item.platformAdminOnly || isPlatformAdmin)
  const links = items.map((item) => (
    <SidebarLink
      key={item.href}
      item={item}
      pathname={pathname}
      collapsed={collapsed}
      team={team}
      onNavigate={onNavigate}
    />
  ))

  // The icon rail has no room for titles: groups are separated by a rule and always shown.
  if (!section.title || collapsed) {
    return (
      <div className="flex flex-col gap-px">
        {section.title && collapsed ? <div className="mx-2 my-2 border-t border-border" /> : null}
        {links}
      </div>
    )
  }
  const id = `nav-section-${section.title.toLowerCase().replace(/\W+/g, "-")}`
  return (
    <div className="flex flex-col gap-px">
      <button
        type="button"
        onClick={toggle}
        aria-expanded={open}
        aria-controls={id}
        className="group flex items-center justify-between rounded-md px-2.5 pb-1 pt-4 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
      >
        {section.title}
        <FontAwesomeIcon
          icon={faChevronRight}
          className={cn(
            "size-2.5 opacity-0 transition-[transform,opacity] duration-200 group-hover:opacity-100 group-focus-visible:opacity-100 motion-reduce:transition-none",
            open && "rotate-90",
            !open && "opacity-100",
          )}
        />
      </button>
      <Collapsible open={open} id={id}>
        <div className="flex flex-col gap-px">{links}</div>
      </Collapsible>
    </div>
  )
}

function SidebarLink({
  item,
  pathname,
  collapsed,
  team,
  onNavigate,
}: {
  item: NavItem
  pathname: string
  collapsed: boolean
  team: string
  onNavigate?: () => void
}) {
  const active = isActive(item, pathname)
  // Projects opens into the team's project → environment → service tree.
  const tree = item.href === "/projects" && team && !collapsed
  const [treeOpen, toggleTree] = useNavOpen("tree:projects", true)
  const link = (
    <Link
      href={item.href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      title={collapsed ? item.label : undefined}
      className={cn(
        "flex h-8 min-w-0 flex-1 items-center gap-2.5 rounded-md px-2.5 text-sm transition-colors",
        active && pathname === item.href
          ? "bg-selected font-medium text-foreground"
          : active
            ? "font-medium text-foreground hover:bg-accent"
            : "text-muted-foreground hover:bg-accent hover:text-foreground",
        collapsed && "justify-center px-0",
      )}
    >
      {item.icon ? <FontAwesomeIcon icon={item.icon} className="size-3.5 shrink-0" /> : null}
      {collapsed ? <span className="sr-only">{item.label}</span> : <span className="truncate">{item.label}</span>}
    </Link>
  )
  if (!tree) return link
  return (
    <div className="flex flex-col">
      <div className="flex items-center">
        {link}
        <button
          type="button"
          onClick={toggleTree}
          aria-expanded={treeOpen}
          aria-label={treeOpen ? "Hide project tree" : "Show project tree"}
          className="flex size-7 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground"
        >
          <FontAwesomeIcon
            icon={faChevronRight}
            className={cn("size-2.5 transition-transform duration-200 motion-reduce:transition-none", treeOpen && "rotate-90")}
          />
        </button>
      </div>
      <Collapsible open={treeOpen}>
        <ProjectTree team={team} onNavigate={onNavigate} />
      </Collapsible>
    </div>
  )
}

/** Desktop left sidebar (lg+). Collapses to an icon rail; the choice is kept in a cookie. */
export function Sidebar({
  isPlatformAdmin,
  team,
  collapsed,
  onToggle,
}: {
  isPlatformAdmin: boolean
  team?: string
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
        <SidebarNav isPlatformAdmin={isPlatformAdmin} team={team} collapsed={collapsed} />
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
