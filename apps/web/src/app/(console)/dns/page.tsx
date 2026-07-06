import { CreateRecordForm } from "@/components/dns/dns-record-controls"
import { DnsImportExport } from "@/components/dns/dns-import-export"
import { DnsRecordsTable } from "@/components/dns/dns-records-table"
import { ZoneSelector } from "@/components/dns/zone-selector"
import { ZoneTools } from "@/components/dns/zone-tools"
import { ZoneTraffic } from "@/components/dns/zone-traffic"
import { EmptyState } from "@/components/ui/empty-state"
import { PageHeader, RefreshLink } from "@/components/ui/page-header"
import { ProviderCard } from "@/components/ui/provider-card"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { DNSResponse, ZoneAnalytics, ZoneSettings } from "@/lib/types"

type DnsPageProps = {
  searchParams: Promise<{ refresh?: string; zone?: string }>
}

export default async function DnsPage({ searchParams }: DnsPageProps) {
  const session = await requireConsoleSession()
  const params = await searchParams
  const dns = await fetchBackend<DNSResponse>("/dns", {
    token: session.token,
    searchParams: {
      refresh: params.refresh === "1" ? "1" : undefined,
      zone: params.zone,
    },
  })

  const [settings, analytics] = dns.selected_zone
    ? await Promise.all([
        fetchBackend<ZoneSettings>(`/dns/zones/${dns.selected_zone}/settings`, {
          token: session.token,
        }).catch(() => null),
        fetchBackend<ZoneAnalytics>(`/dns/zones/${dns.selected_zone}/analytics`, {
          token: session.token,
          searchParams: { days: "7" },
        }).catch(() => null),
      ])
    : [null, null]

  const selectedZoneName =
    dns.zones.find((zone) => zone.id === dns.selected_zone)?.name ?? dns.selected_zone

  const refreshHref = params.zone ? `/dns?refresh=1&zone=${params.zone}` : "/dns?refresh=1"

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Cloudflare DNS"
        title="DNS"
        description="Zone and record management with tenant-scoped backend handling."
        action={<RefreshLink href={refreshHref} label="Refresh DNS" />}
      />

      {dns.providers.length > 0 ? (
        <section className="grid gap-3 md:grid-cols-3">
          {dns.providers.map((provider) => (
            <ProviderCard key={provider.name} provider={provider} />
          ))}
        </section>
      ) : null}

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-border bg-muted p-4">
        <ZoneSelector zones={dns.zones} selected={dns.selected_zone} />
        <span className="text-sm text-muted-foreground">{dns.zones.length} zones</span>
      </div>

      {dns.selected_zone ? (
        <section className="space-y-4">
          {analytics ? (
            <div className="rounded-2xl border border-border bg-muted p-6">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold">Traffic</h2>
                <span className="font-mono text-sm text-muted-foreground">{selectedZoneName} · last 7 days</span>
              </div>
              <div className="mt-4">
                <ZoneTraffic analytics={analytics} />
              </div>
            </div>
          ) : null}

          <CreateRecordForm zoneId={dns.selected_zone} />
          <DnsRecordsTable zoneId={dns.selected_zone} records={dns.records} />

          <div className="grid gap-4 lg:grid-cols-2">
            <DnsImportExport zoneId={dns.selected_zone} zoneName={selectedZoneName} />
            {settings ? <ZoneTools zoneId={dns.selected_zone} settings={settings} /> : null}
          </div>
        </section>
      ) : (
        <EmptyState title="No zones returned." />
      )}
    </div>
  )
}
