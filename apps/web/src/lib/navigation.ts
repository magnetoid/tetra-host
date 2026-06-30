import type { IconDefinition } from "@fortawesome/fontawesome-svg-core"

import {
  faBox,
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
  { href: "/sites", label: "Sites", icon: faServer },
  { href: "/apps", label: "Apps", icon: faBox },
  { href: "/mail", label: "Mail", icon: faEnvelope },
  { href: "/dns", label: "DNS", icon: faGlobe },
  { href: "/admin", label: "Admin", icon: faUserShield },
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
