import { DomainsManager } from "@/components/domains/domains-manager"
import { PageHeader } from "@/components/ui/page-header"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { DomainRecord, InstalledApp } from "@/lib/types"

export default async function DomainsPage() {
  const session = await requireConsoleSession()

  const [domains, apps] = await Promise.all([
    fetchBackend<DomainRecord[]>("/domains", { token: session.token }).catch(() => []),
    fetchBackend<InstalledApp[]>("/apps", { token: session.token }).catch(() => []),
  ])

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Edge"
        title="Domains"
        description="Attach your own domains to deployed apps — ownership is verified with a single TXT record."
      />
      <DomainsManager domains={domains} apps={apps} />
    </div>
  )
}
