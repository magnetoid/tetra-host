import { AppMarketplace } from "@/components/apps/app-marketplace"
import { InstalledApps } from "@/components/apps/installed-apps"
import { PageHeader, RefreshLink } from "@/components/ui/page-header"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { AppTemplate, InstalledApp } from "@/lib/types"

export default async function AppsPage() {
  const session = await requireConsoleSession()
  const [catalog, installed] = await Promise.all([
    fetchBackend<AppTemplate[]>("/apps/catalog", { token: session.token }).catch(() => [] as AppTemplate[]),
    fetchBackend<InstalledApp[]>("/apps", { token: session.token }).catch(() => [] as InstalledApp[]),
  ])

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Tetra Engine"
        title="App catalog"
        description="Install pre-defined Docker apps in one click — run directly by Tetra's own engine."
        action={<RefreshLink href="/apps" label="Refresh" />}
      />

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
