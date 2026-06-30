import Link from "next/link"
import { notFound } from "next/navigation"

import { Card } from "@/components/ui/card"
import { PageHeader } from "@/components/ui/page-header"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { ProjectRecord } from "@/lib/types"

type DomainsPageProps = {
  params: Promise<{ id: string }>
}

export default async function DomainsPage({ params }: DomainsPageProps) {
  const session = await requireConsoleSession()
  const { id } = await params

  const projects = await fetchBackend<ProjectRecord[]>("/projects", {
    token: session.token,
  }).catch(() => [] as ProjectRecord[])

  const project = projects.find((p) => p.id === id)
  if (!project) {
    notFound()
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Networking"
        title="Domains"
        description="Primary domain assigned to this project. Manage DNS records in the DNS section."
      />

      <Card>
        <h3 className="mb-3 text-sm font-medium text-zinc-400">Primary domain</h3>
        {project.primary_domain ? (
          <div className="flex items-center justify-between gap-4">
            <a
              href={`https://${project.primary_domain}`}
              target="_blank"
              rel="noreferrer"
              className="font-mono text-sm text-zinc-200 underline-offset-2 hover:text-white hover:underline"
            >
              {project.primary_domain}
            </a>
            <Link
              href="/dns"
              className="shrink-0 rounded-lg border border-border px-3 py-1.5 text-sm text-zinc-300 transition hover:bg-zinc-900"
            >
              Manage DNS &rarr;
            </Link>
          </div>
        ) : (
          <p className="text-sm text-zinc-500">No primary domain configured for this project.</p>
        )}
      </Card>

      <p className="text-sm text-zinc-500">
        DNS records for this domain are managed globally in the{" "}
        <Link href="/dns" className="text-zinc-300 underline underline-offset-2 hover:text-white">
          DNS section
        </Link>
        .
      </p>
    </div>
  )
}
