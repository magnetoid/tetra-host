import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"

import { faCircleCheck } from "@/lib/icons"
import type { MailDomainCreateResult } from "@/lib/types"

const DNS_DOT: Record<string, string> = {
  created: "bg-status-ok",
  skipped: "bg-status-warn",
  failed: "bg-status-err",
}

/** Post-provisioning summary: which MX/SPF/DKIM/DMARC records were wired, plus
 *  the DKIM TXT value to copy if the zone isn't on Cloudflare. */
export function DnsReport({ report }: { report: MailDomainCreateResult }) {
  return (
    <div className="mt-5 rounded-xl border border-border bg-background p-4">
      <div className="flex items-center gap-2 text-sm font-medium text-status-ok">
        <FontAwesomeIcon icon={faCircleCheck} className="h-4 w-4" />
        {report.domain} is ready
        {report.dns_zone ? (
          <span className="font-normal text-muted-foreground">· DNS in {report.dns_zone}</span>
        ) : null}
      </div>

      {report.dns_records.length > 0 ? (
        <ul className="mt-3 space-y-1.5">
          {report.dns_records.map((r) => (
            <li key={`${r.record_type}-${r.name}`} className="flex items-center gap-2 text-xs">
              <span
                className={`size-2 shrink-0 rounded-full ${DNS_DOT[r.status] ?? "bg-muted-foreground"}`}
              />
              <span className="font-mono font-medium">{r.record_type}</span>
              <span className="truncate font-mono text-muted-foreground">{r.name}</span>
              <span className="ml-auto capitalize text-muted-foreground">{r.status}</span>
            </li>
          ))}
        </ul>
      ) : null}

      {report.dkim_txt ? (
        <div className="mt-3">
          <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            DKIM ({report.dkim_name})
          </div>
          <pre className="mt-1 overflow-x-auto rounded-lg border border-border bg-card p-3 font-mono text-[11px] leading-relaxed">
            {report.dkim_txt}
          </pre>
        </div>
      ) : null}

      {report.relay_assigned ? (
        <p className="mt-3 text-xs text-muted-foreground">
          Outbound relay assigned for deliverability.
        </p>
      ) : null}
    </div>
  )
}
