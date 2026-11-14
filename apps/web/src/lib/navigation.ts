import type { IconDefinition } from "@fortawesome/fontawesome-svg-core"

import {
  faBug,
  faBuilding,
  faChartBar,
  faChartLine,
  faClockRotateLeft,
  faCloud,
  faCoins,
  faEarthAmericas,
  faEnvelope,
  faFolder,
  faGaugeHigh,
  faGlobe,
  faHeartPulse,
  faKey,
  faLayerGroup,
  faListCheck,
  faRocket,
  faServer,
  faStore,
  faUserShield,
  faUsers,
  faWandSparkles,
} from "@/lib/icons"

/**
 * Console navigation model.
 *
 * The console follows the hierarchy platform → team → project → environment →
 * service (ADR 0019). The left sidebar shows the menu of the scope you are in, plus
 * a "back" link to the scope above. `resolveScope()` maps a pathname onto a scope;
 * `sidebarFor()` returns that scope's menu. Both are pure so they are unit-tested
 * and shared by the sidebar, the mobile drawer, the breadcrumbs and ⌘K.
 *
 * Projects and environments live at `/projects/{project}/{environment}` and keep
 * the team menu. A service keeps its own address: an app is an engine stack at
 * `/apps/{stack}/…`, a database is `/databases/{id}`. Their project and
 * environment come from `ScopeLabels`, set by the page that looked them up.
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
  | { kind: "project"; project: string; environment?: string }
  | { kind: "app"; app: string }
  | { kind: "database"; id: string }

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
      { href: "/projects", label: "Projects", icon: faFolder },
    ],
  },
  {
    title: "Network",
    items: [
      { href: "/domains", label: "Domains", icon: faEarthAmericas },
      { href: "/dns", label: "DNS", icon: faGlobe },
      { href: "/mail", label: "Mail", icon: faEnvelope },
    ],
  },
  {
    title: "Operate",
    items: [
      { href: "/deploys", label: "Activity", icon: faServer },
      { href: "/jobs", label: "Jobs", icon: faListCheck },
      { href: "/monitors", label: "Uptime", icon: faHeartPulse },
    ],
  },
  {
    title: "Team",
    items: [
      { href: "/team", label: "Members", icon: faUsers },
      { href: "/usage", label: "Usage", icon: faChartBar },
    ],
  },
  {
    title: "Add-ons",
    items: [
      { href: "/marketplace", label: "Marketplace", icon: faStore },
      { href: "/storage", label: "Storage", icon: faCloud },
      { href: "/ai", label: "AI", icon: faWandSparkles },
    ],
  },
]

/** Flat list of team-scope destinations (⌘K, tests). */
export const consoleNavItems: NavItem[] = teamSections.flatMap((s) => s.items)

// ── Project / environment ─────────────────────────────────────────────────

export function projectHref(project: string, environment?: string): string {
  const base = `/projects/${encodeURIComponent(project)}`
  return environment ? `${base}/${encodeURIComponent(environment)}` : base
}

// ── Services ──────────────────────────────────────────────────────────────

/** Team-scope paths under /apps that are not an app (the catalog). */
const APP_SCOPE_EXCLUDED = new Set(["catalog", "install"])

export function appNavItems(app: string): NavItem[] {
  const base = `/apps/${encodeURIComponent(app)}`
  return [
    { href: `${base}/deployments`, label: "Deployments", icon: faRocket },
    { href: `${base}/compute`, label: "Compute", icon: faGaugeHigh },
    { href: `${base}/env`, label: "Variables", icon: faKey },
    { href: `${base}/metrics`, label: "Metrics", icon: faChartLine },
    { href: `${base}/errors`, label: "Errors", icon: faBug },
  ]
}

export function databaseNavItems(id: string): NavItem[] {
  return [{ href: `/databases/${encodeURIComponent(id)}`, label: "Overview", icon: faGaugeHigh, exact: true }]
}

// ── Resolution ────────────────────────────────────────────────────────────

function underPrefix(pathname: string, prefix: string): boolean {
  return pathname === prefix || pathname.startsWith(`${prefix}/`)
}

export function resolveScope(pathname: string, isPlatformAdmin: boolean): Scope {
  if (isPlatformAdmin && superAdminPaths.some((p) => underPrefix(pathname, p))) {
    return { kind: "platform" }
  }
  const project = pathname.match(/^\/projects\/([^/]+)(?:\/([^/]+))?/)
  if (project) {
    const environment = project[2] ? decodeURIComponent(project[2]) : undefined
    return { kind: "project", project: decodeURIComponent(project[1]), ...(environment ? { environment } : {}) }
  }
  const app = pathname.match(/^\/apps\/([^/]+)/)
  if (app && !APP_SCOPE_EXCLUDED.has(app[1])) {
    return { kind: "app", app: decodeURIComponent(app[1]) }
  }
  const database = pathname.match(/^\/databases\/([^/]+)/)
  if (database) return { kind: "database", id: decodeURIComponent(database[1]) }
  return { kind: "team" }
}

/**
 * Human names for the current scope. The URL only carries slugs and ids, so the
 * page that looked the entity up publishes them (see `SetScopeLabels`).
 */
export type ScopeLabels = {
  team?: string
  /** The service's display name (app or database). */
  app?: string
  project?: string
  projectSlug?: string
  environment?: string
  environmentSlug?: string
}

/** Where a service's "back" link goes: its environment when known, else Projects. */
function serviceBack(labels: ScopeLabels): { href: string; label: string } {
  if (labels.projectSlug && labels.environmentSlug) {
    return {
      href: projectHref(labels.projectSlug, labels.environmentSlug),
      label: labels.project || labels.projectSlug,
    }
  }
  return { href: "/projects", label: "Projects" }
}

export function sidebarFor(
  scope: Scope,
  isPlatformAdmin: boolean,
  labels: ScopeLabels = {},
): SidebarModel {
  switch (scope.kind) {
    case "platform":
      return { sections: platformSections }
    case "team":
    case "project":
      return {
        back: isPlatformAdmin ? { href: SUPER_ADMIN_ROOT, label: "Platform" } : undefined,
        sections: teamSections,
      }
    case "app":
      return { back: serviceBack(labels), sections: [{ items: appNavItems(scope.app) }] }
    case "database":
      return { back: serviceBack(labels), sections: [{ items: databaseNavItems(scope.id) }] }
  }
}

export function isActive(item: NavItem, pathname: string): boolean {
  return item.exact ? pathname === item.href : underPrefix(pathname, item.href)
}

/** The active item of a sidebar model, if any (used for the page crumb). */
export function activeItem(model: SidebarModel, pathname: string): NavItem | undefined {
  const items = model.sections.flatMap((s) => s.items)
  // Prefer the longest matching href when several items match the path.
  return items
    .filter((item) => isActive(item, pathname))
    .sort((a, b) => b.href.length - a.href.length)[0]
}

export type Crumb = { label: string; href?: string }

/** Breadcrumb trail: Platform / team / project / environment / service [/ page].
 * The last crumb has no href. */
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
  if (scope.kind === "project") {
    crumbs.push({ label: labels.project || scope.project, href: projectHref(scope.project) })
    if (scope.environment) {
      crumbs.push({
        label: labels.environment || scope.environment,
        href: projectHref(scope.project, scope.environment),
      })
    }
  }
  if ((scope.kind === "app" || scope.kind === "database") && labels.projectSlug) {
    crumbs.push({ label: labels.project || labels.projectSlug, href: projectHref(labels.projectSlug) })
    if (labels.environmentSlug) {
      crumbs.push({
        label: labels.environment || labels.environmentSlug,
        href: projectHref(labels.projectSlug, labels.environmentSlug),
      })
    }
  }
  if (scope.kind === "app") {
    crumbs.push({ label: labels.app || scope.app, href: appNavItems(scope.app)[0].href })
  }
  if (scope.kind === "database") {
    crumbs.push({ label: labels.app || "Database", href: databaseNavItems(scope.id)[0].href })
  }
  if (scope.kind !== "project") {
    const page = activeItem(sidebarFor(scope, isPlatformAdmin, labels), pathname)
    const isScopeRoot = !page || page.exact
    if (page && !isScopeRoot) crumbs.push({ label: page.label, href: page.href })
  }
  const last = crumbs[crumbs.length - 1]
  if (last) delete last.href
  return crumbs
}

export const publicNavItems: NavItem[] = [
  { href: "/docs", label: "Docs" },
  { href: "/status", label: "Status" },
  { href: "/auth/login", label: "Sign in" },
]
