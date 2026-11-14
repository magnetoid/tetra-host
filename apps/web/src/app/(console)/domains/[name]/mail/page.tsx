import { BulkMailboxImport } from "@/components/mail/bulk-mailbox-import"
import { MailManager } from "@/components/mail/mail-manager"
import { QuarantinePanel } from "@/components/mail/quarantine-panel"
import { DegradedBanner } from "@/components/ui/degraded-banner"
import { EmptyState } from "@/components/ui/empty-state"
import { RefreshLink } from "@/components/ui/page-header"
import { requireConsoleSession } from "@/lib/auth"
import { domainHref, findDomain, isUnder } from "@/lib/domains"
import { loadDomainsOverview } from "@/lib/domains-server"
import { PANEL_PUBLIC_URL } from "@/lib/env"
import { degradedSources, fetchDegraded } from "@/lib/fetch-degraded"
import type { MailResponse } from "@/lib/types"

/** Mail for this domain (and its subdomains): mail domains, mailboxes, quarantine. */
export default async function DomainMailPage({
  params,
  searchParams,
}: {
  params: Promise<{ name: string }>
  searchParams: Promise<{ refresh?: string }>
}) {
  const session = await requireConsoleSession()
  const [{ name: raw }, query] = await Promise.all([params, searchParams])
  const [overview, mailRes] = await Promise.all([
    loadDomainsOverview(session.token),
    fetchDegraded<MailResponse>(
      "/mail",
      "Mail",
      { providers: [], domains: [], mailboxes: [] },
      { token: session.token, searchParams: { refresh: query.refresh === "1" ? "1" : undefined } },
    ),
  ])
  const entry = findDomain(overview.domains, raw)
  if (!entry) return null
  const name = entry.name
  const mail = mailRes.data
  if (mail.providers.length === 0) {
    return (
      <section className="space-y-4">
        <DegradedBanner sources={degradedSources([mailRes])} />
        <EmptyState
          title="Mail isn't connected yet"
          description="Mail runs on a Mailcow instance. A platform admin sets MAILCOW_URL and MAILCOW_API_KEY to turn on mail domains and mailboxes."
        />
      </section>
    )
  }

  const domains = mail.domains.filter((d) => isUnder(d.domain_name, name))
  const mailboxes = mail.mailboxes.filter((m) => isUnder(m.domain, name))

  return (
    <section className="space-y-6">
      <div className="flex justify-end">
        <RefreshLink href={`${domainHref(name, "mail")}?refresh=1`} label="Refresh" />
      </div>
      <DegradedBanner sources={degradedSources([mailRes])} />
      <MailManager
        domains={domains}
        mailboxes={mailboxes}
        appDomains={[name]}
        webmailBase={PANEL_PUBLIC_URL}
      />
      {domains.length > 0 ? <BulkMailboxImport domains={domains} /> : null}
      {domains.length > 0 ? <QuarantinePanel domain={name} /> : null}
    </section>
  )
}
