export type NavItem = {
  href: string
  label: string
}

export const consoleNavItems: NavItem[] = [
  { href: "/dashboard", label: "Overview" },
  { href: "/sites", label: "Sites" },
  { href: "/mail", label: "Mail" },
  { href: "/dns", label: "DNS" },
  { href: "/admin", label: "Admin" },
]

export const publicNavItems: NavItem[] = [
  { href: "/docs", label: "Docs" },
  { href: "/auth/login", label: "Sign in" },
]
