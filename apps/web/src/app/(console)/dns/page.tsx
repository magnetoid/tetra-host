import Link from "next/link"

import { EmptyState } from "@/components/ui/empty-state"
import { PageHeader, RefreshLink } from "@/components/ui/page-header"
import { ProviderCard } from "@/components/ui/provider-card"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { DNSResponse } from "@/lib/types"
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

        <div className="rounded-2xl border border-border bg-muted p-6">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">DNS records</h2>
            <span className="text-sm text-zinc-500">{dns.records.length} shown</span>
          </div>
          <div className="mt-4 overflow-hidden rounded-2xl border border-border">
            <table className="min-w-full divide-y divide-border text-sm">
              <thead className="bg-background/60 text-left text-zinc-500">
                <tr>
                  <th className="px-4 py-3 font-medium">Type</th>
                  <th className="px-4 py-3 font-medium">Name</th>
                  <th className="px-4 py-3 font-medium">Content</th>
                  <th className="px-4 py-3 font-medium">TTL</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border bg-background">
                {dns.records.length > 0 ? (
                  dns.records.map((record) => (
                    <tr key={record.id}>
                      <td className="px-4 py-3">{record.type}</td>
                      <td className="px-4 py-3 text-zinc-300">{record.name}</td>
                      <td className="px-4 py-3 text-zinc-400">{record.content}</td>
                      <td className="px-4 py-3 text-zinc-400">{record.ttl}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={4} className="px-4 py-6 text-zinc-500">
                      Select a zone to browse records.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </div>
  )
}
