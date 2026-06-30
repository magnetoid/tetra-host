import Link from "next/link"
import { notFound } from "next/navigation"

import { Card } from "@/components/ui/card"
import { PageHeader } from "@/components/ui/page-header"
import { StatusBadge } from "@/components/ui/status-badge"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { ProjectDeploymentRecord, ProjectRecord } from "@/lib/types"
import { formatRelativeLabel } from "@/lib/utils"

type ProjectDetailPageProps = {
  params: Promise<{ id: string }>
}

export default async function ProjectDetailPage({ params }: ProjectDetailPageProps) {
  const session = await requireConsoleSession()
  const { id } = await params

  const [projects, deployments] = await Promise.all([
    fetchBackend<ProjectRecord[]>("/projects", { token: session.token }),
    fetchBackend<ProjectDeploymentRecord[]>(`/projects/${id}/deployments`, {
      token: session.token,
    }).catch(() => [] as ProjectDeploymentRecord[]),
  ])

  const project = projects.find((item) => item.id === id)
  if (!project) {
    notFound()
  }

  const latestDeployment = deployments[0] ?? null

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Project overview"
        title={project.name}
        description="Status at a glance — use the sub-navigation to deploy, manage env vars, or configure domains."
      />

      {/* Status strip */}
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <StatusBadge value={project.environment || "Production"} />
        <StatusBadge value={project.status} />
        {project.primary_domain ? (
          <a
            className="text-zinc-400 hover:text-zinc-200"
            href={`https://${project.primary_domain}`}
            target="_blank"
            rel="noreferrer"
          >
            {project.primary_domain}
          </a>
        ) : null}
        {project.repository ? (
          <span className="text-zinc-600">&middot; {project.repository}</span>
        ) : null}
      </div>

      {/* Latest deployment card */}
      <Card>
        <h3 className="mb-3 text-sm font-medium text-zinc-400">Latest deployment</h3>
        {latestDeployment ? (
          <div className="flex items-center justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="font-mono text-sm text-zinc-200">
                  {latestDeployment.commit
                    ? latestDeployment.commit.slice(0, 7)
                    : latestDeployment.id.slice(0, 7)}
                </span>
                <StatusBadge value={latestDeployment.status} />
              </div>
              <div className="text-xs text-zinc-500">
                {latestDeployment.branch ? `Branch: ${latestDeployment.branch} · ` : ""}
                {formatRelativeLabel(latestDeployment.created_at)}
              </div>
            </div>
            <Link
              href={`/projects/${id}/deployments`}
              className="shrink-0 rounded-lg border border-border px-3 py-1.5 text-sm text-zinc-300 transition hover:bg-zinc-900"
            >
              View all deployments
            </Link>
          </div>
        ) : (
          <p className="text-sm text-zinc-500">No deployments yet.</p>
        )}
      </Card>

      {/* Quick links */}
      <div className="grid gap-3 sm:grid-cols-2">
        <Link
          href={`/projects/${id}/deployments`}
          className="flex items-center justify-between rounded-xl border border-border bg-muted p-4 text-sm text-zinc-300 transition hover:border-zinc-600 hover:bg-zinc-900"
        >
          <span className="font-medium">Deployments</span>
          <span className="text-zinc-500">Trigger &amp; view build logs &rarr;</span>
        </Link>
        <Link
          href={`/projects/${id}/env`}
          className="flex items-center justify-between rounded-xl border border-border bg-muted p-4 text-sm text-zinc-300 transition hover:border-zinc-600 hover:bg-zinc-900"
        >
          <span className="font-medium">Environment variables</span>
          <span className="text-zinc-500">Manage secrets &rarr;</span>
        </Link>
        <Link
          href={`/projects/${id}/domains`}
          className="flex items-center justify-between rounded-xl border border-border bg-muted p-4 text-sm text-zinc-300 transition hover:border-zinc-600 hover:bg-zinc-900"
        >
          <span className="font-medium">Domains</span>
          <span className="text-zinc-500">Primary domain &amp; DNS &rarr;</span>
        </Link>
        <Link
          href={`/projects/${id}/settings`}
          className="flex items-center justify-between rounded-xl border border-border bg-muted p-4 text-sm text-zinc-300 transition hover:border-zinc-600 hover:bg-zinc-900"
        >
          <span className="font-medium">Settings</span>
          <span className="text-zinc-500">Deploy &amp; restart actions &rarr;</span>
        </Link>
      </div>
    </div>
  )
}
