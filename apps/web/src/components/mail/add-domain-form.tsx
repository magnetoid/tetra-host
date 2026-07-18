"use client"

import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import { useState } from "react"

import { DnsReport } from "@/components/mail/dns-report"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { faPlus, faWandSparkles } from "@/lib/icons"
import type { MailDomainCreateResult } from "@/lib/types"

/** Add-a-mail-domain form — the automated bit (DKIM + MX/SPF/DKIM/DMARC wiring). */
export function AddDomainForm({
  quickPicks,
  report,
  busy,
  onAdd,
}: {
  quickPicks: string[]
  report: MailDomainCreateResult | null
  busy: boolean
  /** Runs the provisioning mutation; resolves true on success (so we can clear). */
  onAdd: (domain: string) => Promise<boolean>
}) {
  const [domain, setDomain] = useState("")

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    const ok = await onAdd(domain.trim())
    if (ok) setDomain("")
  }

  return (
    <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
      <div className="flex items-center gap-2">
        <FontAwesomeIcon icon={faWandSparkles} className="h-4 w-4 text-primary" />
        <h2 className="text-lg font-semibold">Add a mail domain</h2>
      </div>
      <p className="mt-1 text-sm text-muted-foreground">
        Provisions DKIM and wires MX, SPF, DKIM, and DMARC in Cloudflare automatically.
      </p>

      {quickPicks.length > 0 ? (
        <div className="mt-4">
          <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Enable mail for an app domain
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {quickPicks.map((d) => (
              <button
                key={d}
                type="button"
                onClick={() => setDomain(d)}
                className="rounded-lg border border-border bg-background px-3 py-1.5 font-mono text-xs transition-colors hover:border-primary/40 hover:bg-accent"
              >
                {d}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      <form onSubmit={submit} className="mt-4 flex flex-wrap gap-2">
        <Input
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
          placeholder="example.com"
          className="max-w-xs flex-1"
          aria-label="Mail domain"
        />
        <Button type="submit" icon={faPlus} disabled={busy || !domain.trim()}>
          {busy ? "Adding…" : "Add domain"}
        </Button>
      </form>

      {report ? <DnsReport report={report} /> : null}
    </section>
  )
}
