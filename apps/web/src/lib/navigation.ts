import type { IconDefinition } from "@fortawesome/fontawesome-svg-core"

import {
  faBox,
  faBug,
  faChartBar,
  faChartLine,
  faCloud,
  faCrown,
  faDatabase,
  faEarthAmericas,
  faEnvelope,
  faGaugeHigh,
  faGear,
  faGlobe,
  faKey,
  faListCheck,
  faServer,
  faStore,
  faTerminal,
  faUsers,
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

/** Sidebar section headers, in display order (grouped by user intent). */
export type NavSection =
  | "Overview"
  | "Deploy"
  | "AI"
  | "Resources"
  | "Networking"
  | "Workspace"
  | "Platform admin"

export const NAV_SECTIONS: NavSection[] = [
  "Overview",
  "Deploy",
  "AI",
  "Resources",
  "Networking",
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
 * The per-app menu. The console sidebar slides to show this set when the route
 * is inside an app (`/projects/<project>/apps/<app>/…`), Vercel-style; the
 * mobile project bar renders the same items. Single source of truth for both.
 */
export function projectNavItems(projectSlug: string, appId: string): ProjectNavItem[] {
  const base = `/projects/${projectSlug}/apps/${appId}`
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

  // Deploy — everything that gets your code running. Deployments + Logs are
  // per-app now, so they live inside a project's app rather than as flat
  // siblings here (tenant > project > app > deployment).
  { section: "Deploy", href: "/projects", label: "Projects", icon: faServer },
  { section: "Deploy", href: "/apps", label: "App catalog", icon: faBox },
  { section: "Deploy", href: "/jobs", label: "Jobs", icon: faListCheck },

  // Resources — the managed services your apps consume.
  { section: "Resources", href: "/databases", label: "Databases", icon: faDatabase },
  { section: "Resources", href: "/storage", label: "Storage", icon: faCloud },
  { section: "Resources", href: "/mail", label: "Mail", icon: faEnvelope },

  // Networking — in the order you use them: attach a domain, then manage its DNS.
  { section: "Networking", href: "/domains", label: "Domains", icon: faEarthAmericas },
  { section: "Networking", href: "/dns", label: "DNS", icon: faGlobe },

  // AI — a first-class pillar (Tetra AI Cloud), not buried in account settings.
  { section: "AI", href: "/ai", label: "Playground", icon: faWandSparkles },

  // Workspace — account-level: spend, teammates, and paid add-ons.
  { section: "Workspace", href: "/usage", label: "Usage", icon: faChartBar },
  { section: "Workspace", href: "/team", label: "Team", icon: faUsers },
  { section: "Workspace", href: "/marketplace", label: "Add-ons", icon: faStore },

  // Platform admin — a single door into the operator hub. Every platform
  // surface (tenants, administrators, plans, AI credits, audit) lives ON the
  // Super Admin page, not as flat sidebar items.
  {
    section: "Platform admin",
    href: "/super-admin",
    label: "Super Admin",
    icon: faCrown,
    platformAdminOnly: true,
  },
]

export const publicNavItems: NavItem[] = [
  { href: "/docs", label: "Docs" },
  { href: "/status", label: "Status" },
  { href: "/auth/login", label: "Sign in" },
]
