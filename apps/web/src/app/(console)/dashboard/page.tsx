import Link from "next/link"

import { faEnvelope, faGlobe, faServer, faTriangleExclamation, faUsers } from "@/lib/icons"

import { ZoneTraffic } from "@/components/dns/zone-traffic"
import { BarList } from "@/components/tremor/bar-list"
import { DonutChart, DonutLegend } from "@/components/tremor/donut-chart"
import { Card } from "@/components/ui/card"
import { PageHeader, RefreshLink } from "@/components/ui/page-header"
import { ProviderCard } from "@/components/ui/provider-card"
import { StatCard } from "@/components/ui/stat-card"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type {
  DashboardResponse,
  DNSResponse,
  MailResponse,
  ProjectRecord,
  ZoneAnalytics,
} from "@/lib/types"

// Provider-health donut: connected → ok, degraded → warn, unconfigured → muted grid.
const HEALTH_COLORS = ["var(--status-ok)", "var(--status-warn)", "var(--chart-grid)"]

export default async function DashboardPage() {
  const session = await requireConsoleSession()
  const dashboard = await fetchBackend<DashboardResponse>("/dashboard", { token: session.token })
  const [projects, mail, dns] = await Promise.all([
    fetchBackend<ProjectRecord[]>("/projects", { token: session.token }).catch(() => []),
    fetchBackend<MailResponse>("/mail", { token: session.token }).catch(() => ({
      providers: [],
      domains: [],
      mailboxes: [],
    })),
    fetchBackend<DNSResponse>("/dns", { token: session.token }).catch(() => ({
      providers: [],
      selected_zone: "",
      zones: [],
      records: [],
    })),
  ])

  const primaryZone = dns.selected_zone || dns.zones[0]?.id || ""
  const analytics = primaryZone
    ? await fetchBackend<ZoneAnalytics>(`/dns/zones/${primaryZone}/analytics`, {
        token: session.token,
        searchParams: { days: "7" },
      }).catch(() => null)
    : null
  const primaryZoneName = dns.zones.find((zone) => zone.id === primaryZone)?.name ?? primaryZone

  const m = dashboard.metrics
  const providerCount = (status: string) =>
    dashboard.providers.filter((p) => p.status === status).length
  const connected = providerCount("connected")

  const health = [
    { name: "Connected", value: connected },
    { name: "Degraded", value: providerCount("degraded") },
    { name: "Not configured", value: providerCount("not_configured") },
  ]

  const resources = [
    { name: "Projects", value: m.projects },
    { name: "Mail domains", value: m.mail_domains },
    { name: "DNS zones", value: m.dns_zones },
    { name: "Admins", value: m.admins },
  ]

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Tetra AI Cloud"
        title="Overview"
        description="A live view of your projects, mail, DNS, and provider health."
        action={
          <div className="flex gap-2">
            <RefreshLink href="/dashboard" label="Refresh" />
            {session.admin.role === "platform_admin" ? (
              <Link
                href="/super-admin"
                className="rounded-lg border border-border px-4 py-2 text-sm font-medium transition hover:bg-accent"
              >
                Super Admin
              </Link>
            ) : null}
          </div>
        }
      />

      {/* Restraint: icons stay neutral; color is reserved for meaning — the
          Unhealthy tile turns red only when something actually needs attention. */}
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <StatCard icon={faServer} label="Projects" value={m.projects} hint={session.admin.tenant_name ?? "Your workspace"} accent="text-primary" />
        <StatCard
          icon={faTriangleExclamation}
          label="Unhealthy"
          value={m.unhealthy_projects}
          hint={m.unhealthy_projects > 0 ? "Need attention" : "All healthy"}
          accent={m.unhealthy_projects > 0 ? "text-status-err" : "text-muted-foreground"}
        />
        <StatCard icon={faEnvelope} label="Mail domains" value={m.mail_domains} hint="Mailcow" accent="text-muted-foreground" />
        <StatCard icon={faGlobe} label="DNS zones" value={m.dns_zones} hint="Cloudflare" accent="text-muted-foreground" />
        <StatCard icon={faUsers} label="Admins" value={m.admins} hint="This workspace" accent="text-muted-foreground" />
      </section>

      {/* Bento: one asymmetric grid mixing the traffic hero, provider health,
          connectivity, resource mix, and per-domain previews at varying tile
          widths. Auto-placement fills gaps gracefully when a tile is absent
          (e.g. no traffic analytics). */}
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
              centerValue={`${connected}/${dashboard.providers.length}`}
              centerLabel="healthy"
            />
          </div>
          <DonutLegend data={health} colors={HEALTH_COLORS} className="mt-4" />
        </Card>

        <Card className="lg:col-span-4">
          <h2 className="font-display text-lg font-semibold">Connectivity</h2>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {dashboard.providers.map((provider) => (
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

        <PreviewPanel
          title="Recent projects"
          href="/projects"
          empty="No projects yet."
          className="lg:col-span-2"
        >
          {projects.slice(0, 3).map((project) => (
            <PreviewItem key={project.id} title={project.name} subtitle={project.primary_domain} mono />
          ))}
        </PreviewPanel>
        <PreviewPanel
          title="Mail domains"
          href="/mail"
          empty="No mail domains yet."
          className="lg:col-span-2"
        >
          {mail.domains.slice(0, 3).map((domain) => (
            <PreviewItem
              key={domain.domain_name}
              title={domain.domain_name}
              subtitle={`${domain.mailboxes} mailboxes · ${domain.aliases} aliases`}
            />
          ))}
        </PreviewPanel>
        <PreviewPanel
          title="DNS zones"
          href="/dns"
          empty="No DNS zones yet."
          className="lg:col-span-2"
        >
          {dns.zones.slice(0, 3).map((zone) => (
            <PreviewItem
              key={zone.id}
              title={zone.name}
              subtitle={[zone.status, zone.account_name].filter(Boolean).join(" · ")}
              mono
            />
          ))}
        </PreviewPanel>
      </section>
    </div>
  )
}

function PreviewPanel({
  title,
  href,
  empty,
  className,
  children,
}: {
  title: string
  href: string
  empty: string
  className?: string
  children: React.ReactNode
}) {
  const items = Array.isArray(children) ? children : [children]
  const hasItems = items.some(Boolean)

  return (
    <Card className={className}>
      <div className="flex items-center justify-between">
        <h2 className="font-display text-lg font-semibold">{title}</h2>
        <Link href={href} className="text-sm text-muted-foreground transition hover:text-foreground">
          View all
        </Link>
      </div>
      <div className="mt-4 space-y-3">
        {hasItems ? (
          children
        ) : (
          <div className="rounded-xl border border-dashed border-border bg-background p-4 text-sm text-muted-foreground">
            {empty}
          </div>
        )}
      </div>
    </Card>
  )
}

function PreviewItem({
  title,
  subtitle,
  mono = false,
}: {
  title: string
  subtitle: string
  mono?: boolean
}) {
  return (
    <div className="rounded-xl border border-border bg-background p-4 transition-colors hover:border-primary/30">
      <div className="font-medium">{title}</div>
      <div className={`mt-1 text-sm text-muted-foreground ${mono ? "font-mono text-xs" : ""}`}>
        {subtitle || "—"}
      </div>
    </div>
  )
}
