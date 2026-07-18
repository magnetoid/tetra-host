import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import Link from "next/link"

import {
  faBuilding,
  faClockRotateLeft,
  faCoins,
  faGaugeHigh,
  faLayerGroup,
  faUserShield,
} from "@/lib/icons"

/** The platform-admin destinations that used to live in the left sidebar —
 *  they now live here, on the Super Admin hub. */
const ADMIN_LINKS = [
  { href: "/tenants", label: "Tenants", icon: faBuilding, desc: "Approve, suspend, and manage tenant organizations." },
  { href: "/admin", label: "Administrators", icon: faUserShield, desc: "Platform administrators and provider readiness." },
  { href: "/plans", label: "Plans", icon: faLayerGroup, desc: "Subscription plans available to tenants." },
  { href: "/credits", label: "AI credits", icon: faCoins, desc: "Fund tenants' prepaid AI credit and track spend." },
  { href: "/audit", label: "Audit log", icon: faClockRotateLeft, desc: "Every audited platform action." },
  { href: "/status", label: "Status page", icon: faGaugeHigh, desc: "Public component-by-component health." },
] as const

/** The Super Admin "Platform administration" menu — every operator surface. */
export function AdminLinks() {
  return (
    <section className="space-y-3">
      <h2 className="font-display text-sm font-semibold uppercase tracking-wider text-muted-foreground">
        Platform administration
      </h2>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {ADMIN_LINKS.map((a) => (
          <Link
            key={a.href}
            href={a.href}
            className="group flex items-start gap-3 rounded-lg border border-border bg-card p-4 shadow-sm transition-colors hover:border-primary/40 hover:bg-accent"
          >
            <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-background text-primary">
              <FontAwesomeIcon icon={a.icon} className="h-4 w-4" />
            </span>
            <div className="min-w-0">
              <div className="font-medium">{a.label}</div>
              <div className="mt-0.5 text-xs text-muted-foreground">{a.desc}</div>
            </div>
            <span className="ml-auto text-muted-foreground transition-transform group-hover:translate-x-0.5">
              →
            </span>
          </Link>
        ))}
      </div>
    </section>
  )
}
