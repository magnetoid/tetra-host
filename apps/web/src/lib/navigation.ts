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
  faCrown,
  faDatabase,
  faEarthAmericas,
  faEnvelope,
  faGaugeHigh,
  faGear,
  faGlobe,
  faKey,
  faLayerGroup,
  faListCheck,
  faRocket,
  faServer,
  faStore,
  faTerminal,
  faUsers,
  faUserShield,
  faWandSparkles,
} from "@/lib/icons"

export type NavItem = {
  href: string
  label: string
  icon?: IconDefinition
  /** Sidebar section this item belongs to (console items only; public nav omits it). */
  section?: NavSection
  /** When true, only visible to admins with role === "platform_admin". */
  platformAdminOnly?: boolean
}

/** Sidebar section headers, in display order. */
export type NavSection =
  | "Overview"
  | "Build & run"
  | "Data"
  | "Services"
  | "Workspace"
  | "Platform admin"

export const NAV_SECTIONS: NavSection[] = [
  "Overview",
  "Build & run",
  "Data",
  "Services",
  "Workspace",
  "Platform admin",
]

export type ProjectNavItem = {
  href: string
  label: string
  icon: IconDefinition
  /** When true, only the exact path matches (no prefix match). */
  exact?: boolean
}

/**
 * The per-project menu. The console sidebar slides to show this set when the
 * route is inside a project (`/projects/<id>/…`), Vercel-style; the mobile
 * project bar renders the same items. Single source of truth for both.
 */
export function projectNavItems(projectId: string): ProjectNavItem[] {
  const base = `/projects/${projectId}`
  return [
    { href: `${base}/deployments`, label: "Deployments", icon: faListCheck },
    { href: `${base}/logs`, label: "Logs", icon: faTerminal },
    { href: `${base}/env`, label: "Env", icon: faKey },
    { href: `${base}/domains`, label: "Domains", icon: faEarthAmericas },
    { href: `${base}/metrics`, label: "Metrics", icon: faChartLine },
    { href: `${base}/errors`, label: "Errors", icon: faBug },
    { href: `${base}/settings`, label: "Settings", icon: faGear },
  ]
}

export const consoleNavItems: NavItem[] = [
  // Overview
  { section: "Overview", href: "/dashboard", label: "Overview", icon: faGaugeHigh },

  // Build & run — everything you ship and operate
  { section: "Build & run", href: "/projects", label: "Projects", icon: faServer },
  { section: "Build & run", href: "/deploys", label: "Deployments", icon: faRocket },
  { section: "Build & run", href: "/apps", label: "Apps", icon: faBox },
  { section: "Build & run", href: "/jobs", label: "Jobs", icon: faListCheck },
  { section: "Build & run", href: "/logs", label: "Logs", icon: faTerminal },

  // Data
  { section: "Data", href: "/databases", label: "Databases", icon: faDatabase },
  { section: "Data", href: "/storage", label: "Storage", icon: faCloud },

  // Services
  { section: "Services", href: "/ai", label: "AI", icon: faWandSparkles },
  { section: "Services", href: "/mail", label: "Mail", icon: faEnvelope },
  { section: "Services", href: "/dns", label: "DNS", icon: faGlobe },
  { section: "Services", href: "/domains", label: "Domains", icon: faEarthAmericas },

  // Workspace — account-level
  { section: "Workspace", href: "/usage", label: "Usage", icon: faChartBar },
  { section: "Workspace", href: "/team", label: "Team", icon: faUsers },
  { section: "Workspace", href: "/marketplace", label: "Marketplace", icon: faStore },

  // Platform admin — Cloud Industry operators only
  {
    section: "Platform admin",
    href: "/super-admin",
    label: "Platform",
    icon: faCrown,
    platformAdminOnly: true,
  },
  {
    section: "Platform admin",
    href: "/admin",
    label: "Administrators",
    icon: faUserShield,
    platformAdminOnly: true,
  },
  {
    section: "Platform admin",
    href: "/tenants",
    label: "Tenants",
    icon: faBuilding,
    platformAdminOnly: true,
  },
  {
    section: "Platform admin",
    href: "/plans",
    label: "Plans",
    icon: faLayerGroup,
    platformAdminOnly: true,
  },
  {
    section: "Platform admin",
    href: "/credits",
    label: "AI credits",
    icon: faCoins,
    platformAdminOnly: true,
  },
  {
    section: "Platform admin",
    href: "/audit",
    label: "Audit log",
    icon: faClockRotateLeft,
    platformAdminOnly: true,
  },
]

export const publicNavItems: NavItem[] = [
  { href: "/docs", label: "Docs" },
  { href: "/status", label: "Status" },
  { href: "/auth/login", label: "Sign in" },
]
