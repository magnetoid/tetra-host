import type { IconDefinition } from "@fortawesome/fontawesome-svg-core"

import {
  faBox,
  faBug,
  faBuilding,
  faChartBar,
  faChartLine,
  faCircleInfo,
  faClockRotateLeft,
  faCloud,
  faCoins,
  faDatabase,
  faEarthAmericas,
  faEnvelope,
  faGaugeHigh,
  faGear,
  faGlobe,
  faHeartPulse,
  faKey,
  faLayerGroup,
  faListCheck,
  faServer,
  faStore,
  faTerminal,
  faUserShield,
  faUsers,
  faWandSparkles,
} from "@/lib/icons"

/**
 * Console navigation model.
 *
 * The console is organised as nested scopes — platform → team → project → app —
 * and the left sidebar only ever shows the menu of the scope you are in, plus a
 * "back" link to the scope above. `resolveScope()` maps a pathname onto a scope;
 * `sidebarFor()` returns that scope's menu. Both are pure so they are unit-tested
 * and shared by the sidebar, the mobile drawer, the breadcrumbs and ⌘K.
 *
 * Until the backend has real projects/environments (redesign step 3) the team
 * scope is the signed-in tenant and a "project" is the Coolify project grouping.
 */

export type NavItem = {
  href: string
  label: string
  icon?: IconDefinition
  /** Only the exact path is active (no prefix match). */
  exact?: boolean
  /** Only visible to admins with role === "platform_admin". */
  platformAdminOnly?: boolean
}

export type NavSection = { title?: string; items: NavItem[] }

export type Scope =
  | { kind: "platform" }
  | { kind: "team" }
  | { kind: "project"; project: string }
  | { kind: "app"; project: string; app: string }

export type SidebarModel = {
  /** Link to the enclosing scope (absent at the top scope). */
  back?: { href: string; label: string }
  sections: NavSection[]
}

// ── Platform (super admin) ────────────────────────────────────────────────

export const SUPER_ADMIN_ROOT = "/super-admin"

export const platformSections: NavSection[] = [
  {
    items: [
      { href: SUPER_ADMIN_ROOT, label: "Overview", icon: faGaugeHigh, exact: true },
      { href: "/tenants", label: "Teams", icon: faBuilding },
    ],
  },
  {
    title: "Business",
    items: [
      { href: "/plans", label: "Plans", icon: faLayerGroup },
      { href: "/credits", label: "AI credits", icon: faCoins },
    ],
  },
  {
    title: "System",
    items: [
      { href: "/admin", label: "Administrators", icon: faUserShield },
      { href: "/audit", label: "Audit log", icon: faClockRotateLeft },
    ],
  },
]

/** A platform-admin destination rendered as a card on the Super Admin hub. */
export type SuperAdminNavItem = {
  href: string
  label: string
  icon: IconDefinition
  desc: string
}

export const superAdminNavItems: SuperAdminNavItem[] = [
  { href: "/tenants", label: "Teams", icon: faBuilding, desc: "Approve, suspend, and manage teams." },
  { href: "/admin", label: "Administrators", icon: faUserShield, desc: "Platform administrators and provider readiness." },
  { href: "/plans", label: "Plans", icon: faLayerGroup, desc: "Subscription plans available to teams." },
  { href: "/credits", label: "AI credits", icon: faCoins, desc: "Fund teams' prepaid AI credit and track spend." },
  { href: "/audit", label: "Audit log", icon: faClockRotateLeft, desc: "Every audited platform action." },
  { href: "/status", label: "Status page", icon: faGaugeHigh, desc: "Public component-by-component health." },
]

/** Route prefixes that belong to the platform scope. */
export const superAdminPaths = [
  SUPER_ADMIN_ROOT,
  ...platformSections.flatMap((s) => s.items.map((i) => i.href)),
]

// ── Team (tenant) ─────────────────────────────────────────────────────────

export const teamSections: NavSection[] = [
  {
    items: [
      { href: "/dashboard", label: "Overview", icon: faGaugeHigh, exact: true },
      { href: "/projects", label: "Projects", icon: faServer },
      { href: "/apps", label: "App catalog", icon: faBox },
    ],
  },
  {
    title: "Operate",
    items: [
      { href: "/jobs", label: "Jobs", icon: faListCheck },
      { href: "/monitors", label: "Uptime", icon: faHeartPulse },
    ],
  },
  {
    title: "Network",
    items: [
      { href: "/domains", label: "Domains", icon: faEarthAmericas },
      { href: "/dns", label: "DNS", icon: faGlobe },
    ],
  },
  {
    title: "Services",
    items: [
      { href: "/mail", label: "Mail", icon: faEnvelope },
      { href: "/databases", label: "Databases", icon: faDatabase },
      { href: "/storage", label: "Storage", icon: faCloud },
      { href: "/ai", label: "AI", icon: faWandSparkles },
    ],
  },
  {
    title: "Team",
    items: [
      { href: "/team", label: "Members", icon: faUsers },
      { href: "/usage", label: "Usage", icon: faChartBar },
      { href: "/marketplace", label: "Add-ons", icon: faStore },
    ],
  },
]

/** Flat list of team-scope destinations (⌘K, tests). */
export const consoleNavItems: NavItem[] = teamSections.flatMap((s) => s.items)

// ── Project and app ───────────────────────────────────────────────────────

export function projectNavItems(projectSlug: string, appId: string): NavItem[] {
  const base = `/projects/${projectSlug}/apps/${appId}`
  return [
    { href: base, label: "Overview", icon: faCircleInfo, exact: true },
    { href: `${base}/deployments`, label: "Deployments", icon: faListCheck },
    { href: `${base}/logs`, label: "Logs", icon: faTerminal },
    { href: `${base}/env`, label: "Variables", icon: faKey },
    { href: `${base}/domains`, label: "Domains", icon: faEarthAmericas },
    { href: `${base}/metrics`, label: "Metrics", icon: faChartLine },
    { href: `${base}/errors`, label: "Errors", icon: faBug },
    { href: `${base}/settings`, label: "Settings", icon: faGear },
  ]
}

function projectSections(projectSlug: string): NavSection[] {
  return [{ items: [{ href: `/projects/${projectSlug}`, label: "Apps", icon: faServer, exact: true }] }]
}

// ── Resolution ────────────────────────────────────────────────────────────

function underPrefix(pathname: string, prefix: string): boolean {
  return pathname === prefix || pathname.startsWith(`${prefix}/`)
}

export function resolveScope(pathname: string, isPlatformAdmin: boolean): Scope {
  if (isPlatformAdmin && superAdminPaths.some((p) => underPrefix(pathname, p))) {
    return { kind: "platform" }
  }
  const match = pathname.match(/^\/projects\/([^/]+)(?:\/apps\/([^/]+))?/)
  if (match) {
    const project = decodeURIComponent(match[1])
    if (match[2]) return { kind: "app", project, app: decodeURIComponent(match[2]) }
    return { kind: "project", project }
  }
  return { kind: "team" }
}

export type ScopeLabels = { team?: string; project?: string; app?: string }

export function sidebarFor(scope: Scope, isPlatformAdmin: boolean, labels: ScopeLabels = {}): SidebarModel {
  switch (scope.kind) {
    case "platform":
      return { sections: platformSections }
    case "team":
      return {
        back: isPlatformAdmin ? { href: SUPER_ADMIN_ROOT, label: "Platform" } : undefined,
        sections: teamSections,
      }
    case "project":
      return {
        back: { href: "/projects", label: labels.team || "Projects" },
        sections: projectSections(scope.project),
      }
    case "app":
      return {
        back: { href: `/projects/${scope.project}`, label: labels.project || scope.project },
        sections: [{ items: projectNavItems(scope.project, scope.app) }],
      }
  }
}

export function isActive(item: NavItem, pathname: string): boolean {
  return item.exact ? pathname === item.href : underPrefix(pathname, item.href)
}

/** The active item of a sidebar model, if any (used for the page crumb). */
export function activeItem(model: SidebarModel, pathname: string): NavItem | undefined {
  const items = model.sections.flatMap((s) => s.items)
  // Prefer the longest matching href so /projects/x/apps/y/logs beats /projects/x/apps/y.
  return items
    .filter((item) => isActive(item, pathname))
    .sort((a, b) => b.href.length - a.href.length)[0]
}

export type Crumb = { label: string; href?: string }

/** Breadcrumb trail: Platform / team / project / app [/ page]. Last crumb has no href. */
export function breadcrumbsFor(
  scope: Scope,
  pathname: string,
  isPlatformAdmin: boolean,
  labels: ScopeLabels,
): Crumb[] {
  const crumbs: Crumb[] = []
  if (isPlatformAdmin) crumbs.push({ label: "Platform", href: SUPER_ADMIN_ROOT })
  if (scope.kind !== "platform") {
    crumbs.push({ label: labels.team || "Team", href: "/dashboard" })
  }
  if (scope.kind === "project" || scope.kind === "app") {
    crumbs.push({ label: labels.project || scope.project, href: `/projects/${scope.project}` })
  }
  if (scope.kind === "app") {
    crumbs.push({ label: labels.app || scope.app, href: `/projects/${scope.project}/apps/${scope.app}` })
  }
  const page = activeItem(sidebarFor(scope, isPlatformAdmin, labels), pathname)
  const isScopeRoot = !page || page.exact
  if (page && !isScopeRoot) crumbs.push({ label: page.label, href: page.href })
  const last = crumbs[crumbs.length - 1]
  if (last) delete last.href
  return crumbs
}

export const publicNavItems: NavItem[] = [
  { href: "/docs", label: "Docs" },
  { href: "/status", label: "Status" },
  { href: "/auth/login", label: "Sign in" },
]
