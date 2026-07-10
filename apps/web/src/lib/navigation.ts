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
  /** When true, only visible to admins with role === "platform_admin". */
  platformAdminOnly?: boolean
}

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
  { href: "/dashboard", label: "Overview", icon: faGaugeHigh },
  { href: "/projects", label: "Projects", icon: faServer },
  { href: "/deploys", label: "Deployments", icon: faRocket },
  { href: "/apps", label: "Apps", icon: faBox },
  { href: "/databases", label: "Databases", icon: faDatabase },
  { href: "/storage", label: "Storage", icon: faCloud },
  { href: "/ai", label: "AI", icon: faWandSparkles },
  { href: "/mail", label: "Mail", icon: faEnvelope },
  { href: "/dns", label: "DNS", icon: faGlobe },
  { href: "/domains", label: "Domains", icon: faEarthAmericas },
  { href: "/marketplace", label: "Marketplace", icon: faStore },
  { href: "/admin", label: "Admin", icon: faUserShield },
  { href: "/usage", label: "Usage", icon: faChartBar },
  {
    href: "/super-admin",
    label: "Super Admin",
    icon: faCrown,
    platformAdminOnly: true,
  },
  {
    href: "/plans",
    label: "Plans",
    icon: faLayerGroup,
    platformAdminOnly: true,
  },
  {
    href: "/credits",
    label: "AI credits",
    icon: faKey,
    platformAdminOnly: true,
  },
  {
    href: "/tenants",
    label: "Tenants",
    icon: faUsers,
    platformAdminOnly: true,
  },
]

export const publicNavItems: NavItem[] = [
  { href: "/docs", label: "Docs" },
  { href: "/auth/login", label: "Sign in" },
]
