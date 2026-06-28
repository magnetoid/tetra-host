import Link from "next/link"

import { CreateRecordForm } from "@/components/dns/dns-record-controls"
import { DnsImportExport } from "@/components/dns/dns-import-export"
import { DnsRecordsTable } from "@/components/dns/dns-records-table"
import { ZoneTools } from "@/components/dns/zone-tools"
import { ZoneTraffic } from "@/components/dns/zone-traffic"
import { EmptyState } from "@/components/ui/empty-state"
import { PageHeader, RefreshLink } from "@/components/ui/page-header"
import { ProviderCard } from "@/components/ui/provider-card"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { DNSResponse, ZoneAnalytics, ZoneSettings } from "@/lib/types"
import { cn } from "@/lib/utils"

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

  const refreshHref = params.zone
    ? `/dns?refresh=1&zone=${params.zone}`
    : "/dns?refresh=1"

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Cloudflare DNS"
        title="DNS"
        description="Zone and record visibility with tenant-scoped backend handling."
        action={<RefreshLink href={refreshHref} label="Refresh DNS" />}
      />

      {dns.providers.length > 0 ? (
        <section className="grid gap-3 md:grid-cols-3">
          {dns.providers.map((provider) => (
            <ProviderCard key={provider.name} provider={provider} />
          ))}
        </section>
      ) : null}

      <section className="grid gap-4 lg:grid-cols-[0.8fr_1.2fr]">
        <div className="rounded-2xl border border-border bg-muted p-6">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Zones</h2>
            <span className="text-sm text-zinc-500">{dns.zones.length} total</span>
          </div>
          <div className="mt-4 space-y-3">
            {dns.zones.length > 0 ? (
              dns.zones.map((zone) => (
                <Link
                  key={zone.id}
                  href={`/dns?zone=${zone.id}`}
                  className={cn(
                    "block rounded-xl border px-4 py-4 transition",
                    dns.selected_zone === zone.id
                      ? "border-white bg-background text-white"
                      : "border-border bg-background text-zinc-300 hover:border-zinc-600",
                  )}
                >
                  <div className="font-medium">{zone.name}</div>
                  <div className="mt-1 text-sm text-zinc-500">
                    {[zone.status, zone.account_name].filter(Boolean).join(" · ")}
                  </div>
                </Link>
              ))
            ) : (
              <EmptyState title="No zones returned." />
            )}
          </div>
        </div>

        <div className="space-y-4">
          {dns.selected_zone && analytics ? (
            <div className="rounded-2xl border border-border bg-muted p-6">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold">Traffic</h2>
                <span className="text-sm text-zinc-500">Last 7 days</span>
              </div>
              <div className="mt-4">
                <ZoneTraffic analytics={analytics} />
              </div>
            </div>
          ) : null}
          {dns.selected_zone ? <CreateRecordForm zoneId={dns.selected_zone} /> : null}
          <DnsRecordsTable zoneId={dns.selected_zone} records={dns.records} />
          {dns.selected_zone ? (
            <DnsImportExport zoneId={dns.selected_zone} zoneName={selectedZoneName} />
          ) : null}
          {dns.selected_zone && settings ? (
            <ZoneTools zoneId={dns.selected_zone} settings={settings} />
          ) : null}
        </div>
      </section>
    </div>
  )
}
