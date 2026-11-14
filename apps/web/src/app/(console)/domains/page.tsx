import { AttachDomainForm } from "@/components/domains/domains-manager"
import { DomainsHub } from "@/components/domains/domains-hub"
import { AlertBanner } from "@/components/ui/alert-banner"
import { DegradedBanner } from "@/components/ui/degraded-banner"
import { PageHeader } from "@/components/ui/page-header"
import { requireConsoleSession } from "@/lib/auth"
import { degradedSources, fetchDegraded } from "@/lib/fetch-degraded"
import type { DomainsOverview, InstalledApp } from "@/lib/types"

/** Every domain the team owns, with its DNS, web and mail at a glance (ADR 0019). */
export default async function DomainsPage() {
  const session = await requireConsoleSession()
  const [overviewRes, appsRes] = await Promise.all([
    fetchDegraded<DomainsOverview>(
      "/domains/overview",
      "Domains",
      { providers: [], domains: [] },
      { token: session.token },
    ),
    fetchDegraded<InstalledApp[]>("/apps", "Apps", [], { token: session.token }),
  ])
  const { providers, domains } = overviewRes.data
  const degradedProviders = providers.filter((p) => p.status === "degraded")

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Network"
        title="Domains"
        description="Each domain in one place: its DNS records, the hostnames that route to your services, and its mail."
      />
      <DegradedBanner sources={degradedSources([overviewRes, appsRes])} />
      {degradedProviders.map((p) => (
        <AlertBanner key={p.name} tone="error">
          {p.name} is unreachable, so its part is missing below: {p.detail}
        </AlertBanner>
      ))}

      <DomainsHub domains={domains} />

      <section className="space-y-3">
        <div>
          <h2 className="text-lg font-semibold">Attach a hostname</h2>
          <p className="text-sm text-muted-foreground">
            Point your own hostname at an app. Ownership is checked with one TXT record.
          </p>
        </div>
        <AttachDomainForm apps={appsRes.data} />
      </section>
    </div>
  )
}
