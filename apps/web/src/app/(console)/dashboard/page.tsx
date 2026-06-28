import Link from "next/link"

import { MetricCard } from "@/components/ui/metric-card"
import { PageHeader, RefreshLink } from "@/components/ui/page-header"
import { ProviderCard } from "@/components/ui/provider-card"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { DashboardResponse, DNSResponse, MailResponse, SiteRecord } from "@/lib/types"

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

  const stats = [
    {
      label: "Sites",
      value: dashboard.metrics.sites,
      hint: `${dashboard.metrics.unhealthy_sites} need attention`,
    },
    {
      label: "Mail domains",
      value: dashboard.metrics.mail_domains,
      hint: "Mailcow inventory",
    },
    {
      label: "DNS zones",
      value: dashboard.metrics.dns_zones,
      hint: "Cloudflare inventory",
    },
    {
      label: "Administrators",
      value: dashboard.metrics.admins,
      hint: session.admin.tenant_name ?? "Current tenant",
    },
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

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {stats.map((stat) => (
          <MetricCard key={stat.label} {...stat} />
        ))}
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        <div className="rounded-2xl border border-border bg-muted p-6 lg:col-span-2">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Provider connectivity</h2>
            <span className="rounded-full border border-emerald-900 bg-emerald-950 px-3 py-1 text-xs text-emerald-300">
              Live state
            </span>
          </div>
          <div className="mt-5 grid gap-3 md:grid-cols-3">
            {dashboard.providers.map((provider) => (
              <ProviderCard key={provider.name} provider={provider} />
            ))}
          </div>
        </div>
        <div className="rounded-2xl border border-border bg-muted p-6">
          <h2 className="text-lg font-semibold">Control plane posture</h2>
          <ol className="mt-4 space-y-3 text-sm text-zinc-300">
            <li>1. Signed admin session and protected routes</li>
            <li>2. Provider-backed operational inventory</li>
            <li>3. Tenant-scoped resource visibility</li>
            <li>4. Typed API contracts for the web console</li>
          </ol>
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
