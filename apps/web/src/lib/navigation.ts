import type { IconDefinition } from "@fortawesome/fontawesome-svg-core"

import {
  faBox,
  faChartBar,
  faCrown,
  faEnvelope,
  faGaugeHigh,
  faGlobe,
  faLayerGroup,
  faServer,
  faUsers,
  faUserShield,
} from "@/lib/icons"

export type NavItem = {
  href: string
  label: string
  icon?: IconDefinition
  /** When true, only visible to admins with role === "platform_admin". */
  platformAdminOnly?: boolean
}

export const consoleNavItems: NavItem[] = [
  { href: "/dashboard", label: "Overview", icon: faGaugeHigh },
  { href: "/projects", label: "Projects", icon: faServer },
  { href: "/apps", label: "Apps", icon: faBox },
  { href: "/mail", label: "Mail", icon: faEnvelope },
  { href: "/dns", label: "DNS", icon: faGlobe },
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
