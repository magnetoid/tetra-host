import Link from "next/link"
import { notFound } from "next/navigation"

import { DeployConsole } from "@/components/sites/deploy-console"
import { PageHeader } from "@/components/ui/page-header"
import { StatusBadge } from "@/components/ui/status-badge"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { SiteDeploymentRecord, SiteRecord } from "@/lib/types"

type SiteDetailPageProps = {
  params: Promise<{ id: string }>
}

export default async function SiteDetailPage({ params }: SiteDetailPageProps) {
  const session = await requireConsoleSession()
  const { id } = await params

  const [sites, deployments] = await Promise.all([
    fetchBackend<SiteRecord[]>("/sites", { token: session.token }),
    fetchBackend<SiteDeploymentRecord[]>(`/sites/${id}/deployments`, {
      token: session.token,
    }).catch(() => [] as SiteDeploymentRecord[]),
  ])

  const site = sites.find((item) => item.id === id)
  if (!site) {
    notFound()
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Coolify deploy console"
        title={site.name}
        description="Trigger deploys and watch the build stream in real time."
        action={
          <Link
            href="/sites"
            className="inline-flex rounded-lg border border-border px-4 py-2 text-sm text-zinc-300 transition hover:bg-zinc-900"
          >
            Back to sites
          </Link>
        }
      />

      <div className="flex flex-wrap items-center gap-2 text-sm">
        <StatusBadge value={site.environment || "Production"} />
        <StatusBadge value={site.status} />
        <a
          className="text-zinc-400 hover:text-zinc-200"
          href={`https://${site.primary_domain}`}
          target="_blank"
          rel="noreferrer"
        >
          {site.primary_domain}
        </a>
        {site.repository ? <span className="text-zinc-600">· {site.repository}</span> : null}
      </div>

      <DeployConsole applicationId={site.id} initialDeployments={deployments} />
    </div>
  )
}
