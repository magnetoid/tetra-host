import Link from "next/link"

import { BulkMailboxImport } from "@/components/mail/bulk-mailbox-import"
import { MailManager } from "@/components/mail/mail-manager"
import { QuarantinePanel } from "@/components/mail/quarantine-panel"
import { DegradedBanner } from "@/components/ui/degraded-banner"
import { EmptyState } from "@/components/ui/empty-state"
import { PageHeader, RefreshLink } from "@/components/ui/page-header"
import { ProviderCard } from "@/components/ui/provider-card"
import { requireConsoleSession } from "@/lib/auth"
import { PANEL_PUBLIC_URL } from "@/lib/env"
import { degradedSources, fetchDegraded } from "@/lib/fetch-degraded"
import type { MailResponse, ProjectRecord } from "@/lib/types"

type MailPageProps = {
  searchParams: Promise<{ refresh?: string }>
}

export default async function MailPage({ searchParams }: MailPageProps) {
  const session = await requireConsoleSession()
  const params = await searchParams

  // Mail degrades to a dormant state (never crashes) when Mailcow is unconfigured.
  const [mailRes, projectsRes] = await Promise.all([
    fetchDegraded<MailResponse>(
      "/mail",
      "Mail",
      { providers: [], domains: [], mailboxes: [] },
      {
        token: session.token,
        searchParams: { refresh: params.refresh === "1" ? "1" : undefined },
      },
    ),
    fetchDegraded<ProjectRecord[]>("/projects", "Projects", [], { token: session.token }),
  ])
  const mail = mailRes.data
  const projects = projectsRes.data

  const configured = mail.providers.length > 0
  // Domains you already host on apps → offered as one-click "enable mail" picks.
  // Skip throwaway auto-domains (Coolify's *.sslip.io / *.nip.io previews) — you
  // never want a mailbox on those.
  const appDomains = [...new Set(projects.map((p) => p.primary_domain).filter(Boolean))].filter(
    (d) => !d.includes(".sslip.io") && !d.includes(".nip.io"),
  )

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Mailcow backend"
        title="Mail"
        description="Provision mail domains and mailboxes for the domains you host — DNS is wired automatically."
        action={<RefreshLink href="/mail?refresh=1" label="Refresh" />}
      />

      <DegradedBanner sources={degradedSources([mailRes, projectsRes])} />

      {configured ? (
        <>
          <section className="grid gap-3 md:grid-cols-3">
            {mail.providers.map((provider) => (
              <ProviderCard key={provider.name} provider={provider} />
            ))}
          </section>
          <MailManager
            domains={mail.domains}
            mailboxes={mail.mailboxes}
            appDomains={appDomains}
            webmailBase={PANEL_PUBLIC_URL}
          />
          {mail.domains.length > 0 ? <BulkMailboxImport domains={mail.domains} /> : null}
          {mail.domains.length > 0 ? <QuarantinePanel /> : null}
        </>
      ) : (
        <EmptyState
          title="Mail isn't connected yet"
          description="Mail runs on a Mailcow instance. A platform admin sets MAILCOW_URL + MAILCOW_API_KEY to light up domains, mailboxes, and aliases here."
          action={
            <Link
              href="/docs"
              className="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-1.5 text-sm font-medium text-foreground transition-colors hover:border-primary/40 hover:bg-accent"
            >
              Read the mail setup guide →
            </Link>
          }
        />
      )}
    </div>
  )
}
