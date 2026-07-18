import { DomainsManager } from "@/components/domains/domains-manager"
import { DegradedBanner } from "@/components/ui/degraded-banner"
import { PageHeader } from "@/components/ui/page-header"
import { requireConsoleSession } from "@/lib/auth"
import { degradedSources, fetchDegraded } from "@/lib/fetch-degraded"
import type { DomainRecord, InstalledApp } from "@/lib/types"

export default async function DomainsPage() {
  const session = await requireConsoleSession()

  const [domainsRes, appsRes] = await Promise.all([
    fetchDegraded<DomainRecord[]>("/domains", "Domains", [], { token: session.token }),
    fetchDegraded<InstalledApp[]>("/apps", "Apps", [], { token: session.token }),
  ])
  const domains = domainsRes.data
  const apps = appsRes.data

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Edge"
        title="Domains"
        description="Attach your own domains to deployed apps — ownership is verified with a single TXT record."
      />
      <DegradedBanner sources={degradedSources([domainsRes, appsRes])} />
      <DomainsManager domains={domains} apps={apps} />
    </div>
  )
}
