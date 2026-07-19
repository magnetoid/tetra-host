import Link from "next/link"

import { ZoneTraffic } from "@/components/dns/zone-traffic"
import { BarList } from "@/components/tremor/bar-list"
import { DonutChart, DonutLegend } from "@/components/tremor/donut-chart"
import { Card } from "@/components/ui/card"
import { ProviderCard } from "@/components/ui/provider-card"
import type { DashboardResponse, ProviderSummary, ZoneAnalytics } from "@/lib/types"

// Provider-health donut: connected → ok, degraded → warn, unconfigured → muted grid.
const HEALTH_COLORS = ["var(--status-ok)", "var(--status-warn)", "var(--chart-grid)"]

/**
 * Platform infrastructure overview — provider connectivity, traffic, and the
 * cross-provider resource mix. This is operator-level ("Tetra AI Cloud") context,
 * so it lives on Super Admin rather than the tenant's project Overview.
 */
export function PlatformInfra({
  providers,
  metrics,
  analytics,
  primaryZoneName,
}: {
  providers: ProviderSummary[]
  metrics: DashboardResponse["metrics"]
  analytics: ZoneAnalytics | null
  primaryZoneName: string
}) {
  const connected = providers.filter((p) => p.status === "connected").length
  const health = [
    { name: "Connected", value: connected },
    { name: "Degraded", value: providers.filter((p) => p.status === "degraded").length },
    { name: "Not configured", value: providers.filter((p) => p.status === "not_configured").length },
  ]
  const resources = [
    { name: "Projects", value: metrics.projects },
    { name: "Mail domains", value: metrics.mail_domains },
    { name: "DNS zones", value: metrics.dns_zones },
    { name: "Admins", value: metrics.admins },
  ]

  return (
    <section className="grid auto-rows-min gap-4 lg:grid-cols-6">
      {analytics && analytics.points.length > 0 ? (
        <Card className="lg:col-span-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="font-display text-lg font-semibold">Traffic</h2>
              <p className="mt-1 font-mono text-xs text-muted-foreground">
                {primaryZoneName} · Cloudflare · last 7 days
              </p>
            </div>
            <Link href="/dns" className="text-sm text-muted-foreground transition hover:text-foreground">
              All zones
            </Link>
          </div>
          <div className="mt-4">
            <ZoneTraffic analytics={analytics} />
          </div>
        </Card>
      ) : null}

      <Card className="lg:col-span-2">
        <h2 className="font-display text-lg font-semibold">Provider health</h2>
        <div className="mt-4">
          <DonutChart
            data={health}
            colors={HEALTH_COLORS}
            centerValue={`${connected}/${providers.length}`}
            centerLabel="healthy"
          />
        </div>
        <DonutLegend data={health} colors={HEALTH_COLORS} className="mt-4" />
      </Card>

      <Card className="lg:col-span-4">
        <h2 className="font-display text-lg font-semibold">Connectivity</h2>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {providers.map((provider) => (
            <ProviderCard key={provider.name} provider={provider} />
          ))}
        </div>
      </Card>

      <Card className="lg:col-span-2">
        <h2 className="font-display text-lg font-semibold">Resource mix</h2>
        <div className="mt-5">
          <BarList data={resources} />
        </div>
      </Card>
    </section>
  )
}
