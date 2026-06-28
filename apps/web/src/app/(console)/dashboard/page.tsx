import { AlertTriangle, Globe, Mail, Server, Users } from "lucide-react"
import Link from "next/link"

import { BarList } from "@/components/charts/bar-list"
import { ChartLegend, DonutChart, type DonutSlice } from "@/components/charts/donut-chart"
import { ZoneTraffic } from "@/components/dns/zone-traffic"
import { PageHeader, RefreshLink } from "@/components/ui/page-header"
import { ProviderCard } from "@/components/ui/provider-card"
import { StatCard } from "@/components/ui/stat-card"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type {
  DashboardResponse,
  DNSResponse,
  MailResponse,
  SiteRecord,
  ZoneAnalytics,
} from "@/lib/types"

export default async function DashboardPage() {
  const session = await requireConsoleSession()
  const dashboard = await fetchBackend<DashboardResponse>("/dashboard", { token: session.token })
  const [sites, mail, dns] = await Promise.all([
    fetchBackend<SiteRecord[]>("/sites", { token: session.token }).catch(() => []),
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
  const primaryZoneName =
    dns.zones.find((zone) => zone.id === primaryZone)?.name ?? primaryZone

  const m = dashboard.metrics
  const providerCount = (status: string) =>
    dashboard.providers.filter((p) => p.status === status).length

  const health: DonutSlice[] = [
    { name: "Connected", value: providerCount("connected"), color: "#34d399" },
    { name: "Degraded", value: providerCount("degraded"), color: "#fbbf24" },
    { name: "Not configured", value: providerCount("not_configured"), color: "#52525b" },
  ]

  const resources = [
    { name: "Sites", value: m.sites, color: "bg-violet-500/40" },
    { name: "Mail domains", value: m.mail_domains, color: "bg-emerald-500/40" },
    { name: "DNS zones", value: m.dns_zones, color: "bg-amber-500/40" },
    { name: "Admins", value: m.admins, color: "bg-sky-500/40" },
  ]

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Cloud Industry PaaS"
        title="Overview"
        description="Operational command center with live provider visibility and secured administrative access."
        action={
          <div className="flex gap-2">
            <RefreshLink href="/dashboard" label="Refresh providers" />
            <Link
              href="/admin"
              className="rounded-lg border border-border px-4 py-2 text-sm font-medium transition hover:bg-zinc-900"
            >
              Platform controls
            </Link>
          </div>
        }
      />

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <StatCard icon={Server} label="Sites" value={m.sites} hint={`${m.unhealthy_sites} need attention`} accent="text-violet-400" />
        <StatCard icon={AlertTriangle} label="Unhealthy" value={m.unhealthy_sites} hint="Degraded apps" accent="text-red-400" />
        <StatCard icon={Mail} label="Mail domains" value={m.mail_domains} hint="Mailcow" accent="text-emerald-400" />
        <StatCard icon={Globe} label="DNS zones" value={m.dns_zones} hint="Cloudflare" accent="text-amber-400" />
        <StatCard icon={Users} label="Admins" value={m.admins} hint={session.admin.tenant_name ?? "Current tenant"} accent="text-sky-400" />
      </section>

      {analytics && analytics.points.length > 0 ? (
        <section className="rounded-2xl border border-border bg-muted p-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold">Traffic</h2>
              <p className="mt-1 text-sm text-zinc-500">
                {primaryZoneName} · Cloudflare · last 7 days
              </p>
            </div>
            <Link href="/dns" className="text-sm text-zinc-400 hover:text-white">
              All zones
            </Link>
          </div>
          <div className="mt-4">
            <ZoneTraffic analytics={analytics} />
          </div>
        </section>
      ) : null}

      <section className="grid gap-4 lg:grid-cols-3">
        <div className="rounded-2xl border border-border bg-muted p-6">
          <h2 className="text-lg font-semibold">Provider health</h2>
          <div className="mt-4">
            <DonutChart
              data={health}
              centerLabel={`${providerCount("connected")}/${dashboard.providers.length}`}
              centerSublabel="healthy"
            />
          </div>
          <div className="mt-4">
            <ChartLegend data={health} />
          </div>
        </div>

        <div className="rounded-2xl border border-border bg-muted p-6">
          <h2 className="text-lg font-semibold">Resource mix</h2>
          <div className="mt-5">
            <BarList data={resources} />
          </div>
        </div>

        <div className="rounded-2xl border border-border bg-muted p-6">
          <h2 className="text-lg font-semibold">Connectivity</h2>
          <div className="mt-4 space-y-3">
            {dashboard.providers.map((provider) => (
              <ProviderCard key={provider.name} provider={provider} />
            ))}
          </div>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        <PreviewPanel title="Recent sites" href="/sites" empty="No Coolify applications available yet.">
          {sites.slice(0, 3).map((site) => (
            <PreviewItem key={site.id} title={site.name} subtitle={site.primary_domain} />
          ))}
        </PreviewPanel>
        <PreviewPanel title="Mail domains" href="/mail" empty="Mailcow returned no domains.">
          {mail.domains.slice(0, 3).map((domain) => (
            <PreviewItem
              key={domain.domain_name}
              title={domain.domain_name}
              subtitle={`${domain.mailboxes} mailboxes · ${domain.aliases} aliases`}
            />
          ))}
        </PreviewPanel>
        <PreviewPanel title="DNS zones" href="/dns" empty="Cloudflare returned no zones.">
          {dns.zones.slice(0, 3).map((zone) => (
            <PreviewItem
              key={zone.id}
              title={zone.name}
              subtitle={[zone.status, zone.account_name].filter(Boolean).join(" · ")}
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
  children,
}: {
  title: string
  href: string
  empty: string
  children: React.ReactNode
}) {
  const items = Array.isArray(children) ? children : [children]
  const hasItems = items.some(Boolean)

  return (
    <div className="rounded-2xl border border-border bg-muted p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">{title}</h2>
        <Link href={href} className="text-sm text-zinc-400 hover:text-white">
          View all
        </Link>
      </div>
      <div className="mt-4 space-y-3">
        {hasItems ? (
          children
        ) : (
          <div className="rounded-xl border border-dashed border-border bg-background p-4 text-sm text-zinc-500">
            {empty}
          </div>
        )}
      </div>
    </div>
  )
}

function PreviewItem({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div className="rounded-xl border border-border bg-background p-4">
      <div className="font-medium">{title}</div>
      <div className="mt-1 text-sm text-zinc-500">{subtitle}</div>
    </div>
  )
}
