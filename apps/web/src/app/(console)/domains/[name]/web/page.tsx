import { AttachDomainForm, HostnameList } from "@/components/domains/domains-manager"
import { DegradedBanner } from "@/components/ui/degraded-banner"
import { EmptyState } from "@/components/ui/empty-state"
import { requireConsoleSession } from "@/lib/auth"
import { findDomain, isUnder } from "@/lib/domains"
import { loadDomainsOverview } from "@/lib/domains-server"
import { degradedSources, fetchDegraded } from "@/lib/fetch-degraded"
import type { DomainRecord, InstalledApp } from "@/lib/types"

/** Hostnames of this domain that route to services, and attaching a new one. */
export default async function DomainWebPage({ params }: { params: Promise<{ name: string }> }) {
  const session = await requireConsoleSession()
  const { name } = await params
  const [overview, domainsRes, appsRes] = await Promise.all([
    loadDomainsOverview(session.token),
    fetchDegraded<DomainRecord[]>("/domains", "Hostnames", [], { token: session.token }),
    fetchDegraded<InstalledApp[]>("/apps", "Apps", [], { token: session.token }),
  ])
  const entry = findDomain(overview.domains, name)
  if (!entry) return null

  const hostnames = domainsRes.data.filter((d) => isUnder(d.hostname, entry.name))
  // Where each stack lives, so a hostname links to its service with project · environment.
  const placement = Object.fromEntries(
    entry.hostnames
      .filter((h) => h.service)
      .map((h) => [
        h.stack,
        {
          label: `${h.service!.name} · ${h.service!.project_slug} / ${h.service!.environment_slug}`,
          href: `/apps/${encodeURIComponent(h.stack)}/deployments`,
        },
      ]),
  )

  return (
    <section className="space-y-4">
      <DegradedBanner sources={degradedSources([domainsRes, appsRes])} />
      <AttachDomainForm apps={appsRes.data} placeholder={`www.${entry.name}`} />
      {hostnames.length ? (
        <HostnameList domains={hostnames} placement={placement} />
      ) : (
        <EmptyState
          title={`Nothing routes to ${entry.name} yet`}
          description="Attach a hostname above to serve one of your apps on it."
        />
      )}
    </section>
  )
}
