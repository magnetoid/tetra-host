import type { IconDefinition } from "@fortawesome/fontawesome-svg-core"

import {
  faBox,
  faBug,
  faBuilding,
  faChartBar,
  faChartLine,
  faClockRotateLeft,
  faCloud,
  faCoins,
  faDatabase,
  faEarthAmericas,
  faEnvelope,
  faGaugeHigh,
  faGlobe,
  faHeartPulse,
  faKey,
  faLayerGroup,
  faListCheck,
  faServer,
  faStore,
  faUserShield,
  faUsers,
  faWandSparkles,
} from "@/lib/icons"

/**
 * Console navigation model.
 *
 * The console is organised as nested scopes — platform → team → app — and the
 * left sidebar only ever shows the menu of the scope you are in, plus a "back"
 * link to the scope above. `resolveScope()` maps a pathname onto a scope;
 * `sidebarFor()` returns that scope's menu. Both are pure so they are unit-tested
 * and shared by the sidebar, the mobile drawer, the breadcrumbs and ⌘K.
 *
 * An app is a Tetra Engine stack addressed by its project name (`/apps/{project}/…`).
 * The project and environment levels arrive with the hierarchy screens.
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
  | { kind: "app"; app: string }

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
      { href: "/deploys", label: "Deploys", icon: faServer },
      { href: "/apps", label: "Apps", icon: faBox },
      { href: "/databases", label: "Databases", icon: faDatabase },
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

// ── App ───────────────────────────────────────────────────────────────────

/** Team-scope paths under /apps that are not an app (the catalog). */
const APP_SCOPE_EXCLUDED = new Set(["catalog", "install"])

export function appNavItems(app: string): NavItem[] {
  const base = `/apps/${encodeURIComponent(app)}`
  return [
    { href: `${base}/compute`, label: "Compute", icon: faGaugeHigh },
    { href: `${base}/env`, label: "Variables", icon: faKey },
    { href: `${base}/metrics`, label: "Metrics", icon: faChartLine },
    { href: `${base}/errors`, label: "Errors", icon: faBug },
  ]
}

// ── Resolution ────────────────────────────────────────────────────────────

function underPrefix(pathname: string, prefix: string): boolean {
  return pathname === prefix || pathname.startsWith(`${prefix}/`)
}

export function resolveScope(pathname: string, isPlatformAdmin: boolean): Scope {
  if (isPlatformAdmin && superAdminPaths.some((p) => underPrefix(pathname, p))) {
    return { kind: "platform" }
  }
  const match = pathname.match(/^\/apps\/([^/]+)/)
  if (match && !APP_SCOPE_EXCLUDED.has(match[1])) {
    return { kind: "app", app: decodeURIComponent(match[1]) }
  }
  return { kind: "team" }
}

export type ScopeLabels = { team?: string; app?: string }

export function sidebarFor(scope: Scope, isPlatformAdmin: boolean): SidebarModel {
  switch (scope.kind) {
    case "platform":
      return { sections: platformSections }
    case "team":
      return {
        back: isPlatformAdmin ? { href: SUPER_ADMIN_ROOT, label: "Platform" } : undefined,
        sections: teamSections,
      }
    case "app":
      return {
        back: { href: "/apps", label: "Apps" },
        sections: [{ items: appNavItems(scope.app) }],
      }
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

/** Breadcrumb trail: Platform / team / app [/ page]. Last crumb has no href. */
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
  if (scope.kind === "app") {
    crumbs.push({ label: labels.app || scope.app, href: appNavItems(scope.app)[0].href })
  }
  const page = activeItem(sidebarFor(scope, isPlatformAdmin), pathname)
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
