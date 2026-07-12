import Link from "next/link"
import { notFound } from "next/navigation"

import { EnableMailButton } from "@/components/mail/enable-mail-button"
import { Card } from "@/components/ui/card"
import { PageHeader } from "@/components/ui/page-header"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { MailResponse, ProjectRecord } from "@/lib/types"

type DomainsPageProps = {
  params: Promise<{ app: string }>
}

export default async function DomainsPage({ params }: DomainsPageProps) {
  const session = await requireConsoleSession()
  const { app } = await params

  const [projects, mail] = await Promise.all([
    fetchBackend<ProjectRecord[]>("/projects", { token: session.token }).catch(
      () => [] as ProjectRecord[],
    ),
    fetchBackend<MailResponse>("/mail", { token: session.token }).catch(
      () => ({ providers: [], domains: [], mailboxes: [] }) as MailResponse,
    ),
  ])

  const project = projects.find((p) => p.id === app)
  if (!project) {
    notFound()
  }

  // Offer mail on a real domain only (never Coolify's *.sslip.io/*.nip.io previews).
  const domain = project.primary_domain
  const canHaveMail =
    Boolean(domain) && !domain.includes(".sslip.io") && !domain.includes(".nip.io")
  const mailConfigured = mail.providers.length > 0
  const mailEnabled = mail.domains.some((d) => d.domain_name === domain)

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Networking"
        title="Domains"
        description="This app's domain — manage its DNS and enable mailboxes on it."
      />

      <Card>
        <h3 className="mb-3 text-sm font-medium text-muted-foreground">Primary domain</h3>
        {project.primary_domain ? (
          <div className="flex items-center justify-between gap-4">
            <a
              href={`https://${project.primary_domain}`}
              target="_blank"
              rel="noreferrer"
              className="font-mono text-sm text-foreground underline-offset-2 hover:text-foreground hover:underline"
            >
              {project.primary_domain}
            </a>
            <Link
              href="/dns"
              className="shrink-0 rounded-lg border border-border px-3 py-1.5 text-sm text-foreground transition-colors hover:bg-accent"
            >
              Manage DNS &rarr;
            </Link>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No primary domain configured for this app.</p>
        )}
      </Card>

      {canHaveMail ? (
        <Card>
          <h3 className="mb-1 text-sm font-medium text-muted-foreground">Mail</h3>
          {mailConfigured ? (
            <>
              <p className="mb-3 text-sm text-muted-foreground">
                Add mailboxes on <span className="font-mono text-foreground">{domain}</span> — DNS is
                wired automatically.
              </p>
              <EnableMailButton domain={domain} enabled={mailEnabled} />
            </>
          ) : (
            <p className="text-sm text-muted-foreground">
              Mail isn&apos;t connected yet.{" "}
              <Link href="/mail" className="text-foreground underline underline-offset-2 hover:text-foreground">
                Set up mail
              </Link>{" "}
              to enable mailboxes on this domain.
            </p>
          )}
        </Card>
      ) : null}

      <p className="text-sm text-muted-foreground">
        DNS records for this domain are managed globally in the{" "}
        <Link href="/dns" className="text-foreground underline underline-offset-2 hover:text-foreground">
          DNS section
        </Link>
        .
      </p>
    </div>
  )
}
