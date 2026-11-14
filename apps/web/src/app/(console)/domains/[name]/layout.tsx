import Link from "next/link"
import { notFound } from "next/navigation"

import { DomainTabs } from "@/components/domains/domain-tabs"
import { PageHeader } from "@/components/ui/page-header"
import { requireConsoleSession } from "@/lib/auth"
import { findDomain, mailboxCount } from "@/lib/domains"
import { loadDomainsOverview } from "@/lib/domains-server"

export default async function DomainLayout({
  children,
  params,
}: {
  children: React.ReactNode
  params: Promise<{ name: string }>
}) {
  const session = await requireConsoleSession()
  const { name } = await params
  const overview = await loadDomainsOverview(session.token)
  const entry = findDomain(overview.domains, name)
  if (!entry) notFound()

  return (
    <div className="space-y-6">
      <Link href="/domains" className="text-sm text-muted-foreground hover:text-foreground">
        ← Domains
      </Link>
      <PageHeader eyebrow="Domain" title={entry.name} />
      <DomainTabs
        name={entry.name}
        counts={{
          dns: entry.zone ? undefined : "off",
          web: entry.hostnames.length,
          mail: entry.mail.length ? mailboxCount(entry) : "off",
        }}
      />
      {children}
    </div>
  )
}
