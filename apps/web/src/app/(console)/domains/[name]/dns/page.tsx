import { CreateRecordForm } from "@/components/dns/dns-record-controls"
import { DnsImportExport } from "@/components/dns/dns-import-export"
import { DnsRecordsTable } from "@/components/dns/dns-records-table"
import { ZoneTools } from "@/components/dns/zone-tools"
import { ZoneTraffic } from "@/components/dns/zone-traffic"
import { DegradedBanner } from "@/components/ui/degraded-banner"
import { EmptyState } from "@/components/ui/empty-state"
import { RefreshLink } from "@/components/ui/page-header"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import { domainHref, findDomain } from "@/lib/domains"
import { loadDomainsOverview } from "@/lib/domains-server"
import { degradedSources, fetchDegraded } from "@/lib/fetch-degraded"
import type { DNSResponse, ZoneAnalytics, ZoneSettings } from "@/lib/types"

export default async function DomainDnsPage({
  params,
  searchParams,
}: {
  params: Promise<{ name: string }>
  searchParams: Promise<{ refresh?: string }>
}) {
  const session = await requireConsoleSession()
  const [{ name }, query] = await Promise.all([params, searchParams])
  const entry = findDomain((await loadDomainsOverview(session.token)).domains, name)
  const zoneId = entry?.zone?.id
  if (!entry || !zoneId) {
    return (
      <EmptyState
        title="This domain's DNS isn't on Cloudflare"
        description="Its records are managed wherever its nameservers point. To manage them here, ask your platform admin to add the zone to Cloudflare and assign it to your team."
      />
    )
  }

  const [dns, settingsRes, analyticsRes] = await Promise.all([
    fetchBackend<DNSResponse>("/dns", {
      token: session.token,
      searchParams: { zone: zoneId, refresh: query.refresh === "1" ? "1" : undefined },
    }),
    fetchDegraded<ZoneSettings | null>(`/dns/zones/${zoneId}/settings`, "Zone settings", null, {
      token: session.token,
    }),
    fetchDegraded<ZoneAnalytics | null>(`/dns/zones/${zoneId}/analytics`, "Traffic analytics", null, {
      token: session.token,
      searchParams: { days: "7" },
    }),
  ])

  return (
    <section className="space-y-4">
      <div className="flex justify-end">
        <RefreshLink href={`${domainHref(entry.name, "dns")}?refresh=1`} label="Refresh DNS" />
      </div>
      <DegradedBanner sources={degradedSources([settingsRes, analyticsRes])} />
      {analyticsRes.data ? (
        <div className="rounded-lg border border-border bg-muted p-6">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Traffic</h2>
            <span className="font-mono text-sm text-muted-foreground">last 7 days</span>
          </div>
          <div className="mt-4">
            <ZoneTraffic analytics={analyticsRes.data} />
          </div>
        </div>
      ) : null}
      <CreateRecordForm zoneId={zoneId} />
      <DnsRecordsTable zoneId={zoneId} records={dns.records} />
      <div className="grid gap-4 lg:grid-cols-2">
        <DnsImportExport zoneId={zoneId} zoneName={entry.name} />
        {settingsRes.data ? <ZoneTools zoneId={zoneId} settings={settingsRes.data} /> : null}
      </div>
    </section>
  )
}
