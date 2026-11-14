import { redirect } from "next/navigation"

import { requireConsoleSession } from "@/lib/auth"
import { domainHref } from "@/lib/domains"
import { loadDomainsOverview } from "@/lib/domains-server"

/** DNS moved into Domains (ADR 0019); `/dns?zone=…` lands on that domain's DNS tab. */
export default async function DnsPage({ searchParams }: { searchParams: Promise<{ zone?: string }> }) {
  const session = await requireConsoleSession()
  const { zone } = await searchParams
  if (zone) {
    const overview = await loadDomainsOverview(session.token).catch(() => null)
    const entry = overview?.domains.find((d) => d.zone?.id === zone)
    if (entry) redirect(domainHref(entry.name, "dns"))
  }
  redirect("/domains")
}
