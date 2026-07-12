import Link from "next/link"

import { MailManager } from "@/components/mail/mail-manager"
import { EmptyState } from "@/components/ui/empty-state"
import { PageHeader, RefreshLink } from "@/components/ui/page-header"
import { ProviderCard } from "@/components/ui/provider-card"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { MailResponse, ProjectRecord } from "@/lib/types"

type MailPageProps = {
  searchParams: Promise<{ refresh?: string }>
}

export default async function MailPage({ searchParams }: MailPageProps) {
  const session = await requireConsoleSession()
  const params = await searchParams

  // Mail degrades to a dormant state (never crashes) when Mailcow is unconfigured.
  const [mail, projects] = await Promise.all([
    fetchBackend<MailResponse>("/mail", {
      token: session.token,
      searchParams: { refresh: params.refresh === "1" ? "1" : undefined },
    }).catch(() => ({ providers: [], domains: [], mailboxes: [] }) as MailResponse),
    fetchBackend<ProjectRecord[]>("/projects", { token: session.token }).catch(
      () => [] as ProjectRecord[],
    ),
  ])

  const configured = mail.providers.length > 0
  // Domains you already host on apps → offered as one-click "enable mail" picks.
  const appDomains = [...new Set(projects.map((p) => p.primary_domain).filter(Boolean))]

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Mailcow backend"
        title="Mail"
        description="Provision mail domains and mailboxes for the domains you host — DNS is wired automatically."
        action={<RefreshLink href="/mail?refresh=1" label="Refresh" />}
      />

      {configured ? (
        <>
          <section className="grid gap-3 md:grid-cols-3">
            {mail.providers.map((provider) => (
              <ProviderCard key={provider.name} provider={provider} />
            ))}
          </section>
          <MailManager domains={mail.domains} mailboxes={mail.mailboxes} appDomains={appDomains} />
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
