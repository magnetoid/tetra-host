import type { DomainOverviewEntry } from "@/lib/types"

export type DomainTab = "dns" | "web" | "mail"

export const DOMAIN_TABS: { key: DomainTab; label: string }[] = [
  { key: "dns", label: "DNS" },
  { key: "web", label: "Web" },
  { key: "mail", label: "Mail" },
]

export function domainHref(name: string, tab?: DomainTab): string {
  const base = `/domains/${encodeURIComponent(name)}`
  return tab ? `${base}/${tab}` : base
}

/** True when `hostname` is the apex itself or sits under it. */
export function isUnder(hostname: string, apex: string): boolean {
  const host = hostname.toLowerCase().replace(/\.$/, "")
  const root = apex.toLowerCase()
  return host === root || host.endsWith(`.${root}`)
}

/** The tab a domain opens on: DNS when Cloudflare holds its zone, else Web. */
export function defaultDomainTab(entry: DomainOverviewEntry): DomainTab {
  return entry.zone ? "dns" : "web"
}

export function mailboxCount(entry: DomainOverviewEntry): number {
  return entry.mail.reduce((sum, m) => sum + m.mailboxes, 0)
}

export function findDomain(
  domains: DomainOverviewEntry[],
  name: string,
): DomainOverviewEntry | undefined {
  const wanted = decodeURIComponent(name).toLowerCase().replace(/\.$/, "")
  // Exact apex first; a subdomain (mail.example.com) opens the domain it sits under.
  return (
    domains.find((d) => d.name === wanted) ??
    domains
      .filter((d) => isUnder(wanted, d.name))
      .sort((a, b) => b.name.length - a.name.length)[0]
  )
}
