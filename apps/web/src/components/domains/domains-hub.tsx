import Link from "next/link"

import { EmptyState } from "@/components/ui/empty-state"
import { StatusBadge } from "@/components/ui/status-badge"
import { domainHref, mailboxCount } from "@/lib/domains"
import type { DomainOverviewEntry } from "@/lib/types"

function Muted({ children }: { children: React.ReactNode }) {
  return <span className="text-muted-foreground">{children}</span>
}

/** One row per account domain: is its DNS here, does it have mail, what routes to it. */
export function DomainsHub({ domains }: { domains: DomainOverviewEntry[] }) {
  if (domains.length === 0) {
    return (
      <EmptyState
        title="No domains yet"
        description="Domains appear here once a DNS zone, a mail domain or a hostname for one of your services is added."
      />
    )
  }
  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <table className="w-full text-sm">
        <thead className="bg-muted text-left text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            <th className="px-4 py-3 font-medium">Domain</th>
            <th className="px-4 py-3 font-medium">DNS</th>
            <th className="hidden px-4 py-3 font-medium sm:table-cell">Web</th>
            <th className="hidden px-4 py-3 font-medium sm:table-cell">Mail</th>
          </tr>
        </thead>
        <tbody>
          {domains.map((d) => {
            const verified = d.hostnames.filter((h) => h.status === "verified").length
            const mailboxes = mailboxCount(d)
            return (
              <tr key={d.name} className="border-t border-border">
                <td className="px-4 py-3">
                  <Link href={domainHref(d.name)} className="font-mono font-medium hover:underline">
                    {d.name}
                  </Link>
                </td>
                <td className="px-4 py-3">
                  {d.zone ? <StatusBadge value={d.zone.paused ? "paused" : d.zone.status} /> : <Muted>Not on Cloudflare</Muted>}
                </td>
                <td className="hidden px-4 py-3 sm:table-cell">
                  {d.hostnames.length ? (
                    <span>
                      {d.hostnames.length} hostname{d.hostnames.length === 1 ? "" : "s"}
                      {verified < d.hostnames.length ? (
                        <Muted> · {d.hostnames.length - verified} pending</Muted>
                      ) : null}
                    </span>
                  ) : (
                    <Muted>—</Muted>
                  )}
                </td>
                <td className="hidden px-4 py-3 sm:table-cell">
                  {d.mail.length ? (
                    <span>
                      {mailboxes} mailbox{mailboxes === 1 ? "" : "es"}
                    </span>
                  ) : (
                    <Muted>Off</Muted>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
