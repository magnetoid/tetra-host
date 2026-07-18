import { AppMarketplace } from "@/components/apps/app-marketplace"
import { InstalledApps } from "@/components/apps/installed-apps"
import { DegradedBanner } from "@/components/ui/degraded-banner"
import { PageHeader, RefreshLink } from "@/components/ui/page-header"
import { requireConsoleSession } from "@/lib/auth"
import { degradedSources, fetchDegraded } from "@/lib/fetch-degraded"
import type { AppTemplate, InstalledApp } from "@/lib/types"

export default async function AppsPage() {
  const session = await requireConsoleSession()
  const [catalogRes, installedRes] = await Promise.all([
    fetchDegraded<AppTemplate[]>("/apps/catalog", "Apps catalog", [], { token: session.token }),
    fetchDegraded<InstalledApp[]>("/apps", "Installed apps", [], { token: session.token }),
  ])
  const catalog = catalogRes.data
  const installed = installedRes.data

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Managed containers"
        title="App catalog"
        description="One-click container apps — small Docker services Tetra provisions and runs on managed infrastructure (Cloudflare, Hetzner) and bills as a managed service."
        action={<RefreshLink href="/apps" label="Refresh" />}
      />

      <DegradedBanner sources={degradedSources([catalogRes, installedRes])} />

      <section className="space-y-4">
        <h2 className="text-lg font-semibold">Installed</h2>
        <InstalledApps apps={installed} />
      </section>

      <section className="space-y-4">
        <div className="flex items-end justify-between">
          <h2 className="text-lg font-semibold">Marketplace</h2>
          <span className="text-sm text-muted-foreground">{catalog.length} apps available</span>
        </div>
        <AppMarketplace
          templates={catalog}
          installedProjects={installed.map((app) => app.project)}
        />
      </section>
    </div>
  )
}
