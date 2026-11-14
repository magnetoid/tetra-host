import { notFound, redirect } from "next/navigation"

import { requireConsoleSession } from "@/lib/auth"
import { defaultDomainTab, domainHref, findDomain } from "@/lib/domains"
import { loadDomainsOverview } from "@/lib/domains-server"

/** A domain opens on DNS when Cloudflare holds its zone, else on Web. */
export default async function DomainPage({ params }: { params: Promise<{ name: string }> }) {
  const session = await requireConsoleSession()
  const { name } = await params
  const entry = findDomain((await loadDomainsOverview(session.token)).domains, name)
  if (!entry) notFound()
  redirect(domainHref(entry.name, defaultDomainTab(entry)))
}
