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
            className="font-mono text-xs text-muted-foreground transition-colors hover:text-foreground"
            href={`https://${project.primary_domain}`}
            target="_blank"
            rel="noreferrer"
          >
            {project.primary_domain}
          </a>
        ) : null}
        {project.repository ? (
          <span className="font-mono text-xs text-muted-foreground">
            &middot; {project.repository}
          </span>
        ) : null}
      </div>

      {/* Latest deployment card */}
      <Card>
        <h3 className="mb-3 text-sm font-medium text-muted-foreground">Latest deployment</h3>
        {latestDeployment ? (
          <div className="flex items-center justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="font-mono text-sm text-foreground">
                  {latestDeployment.commit
                    ? latestDeployment.commit.slice(0, 7)
                    : latestDeployment.id.slice(0, 7)}
                </span>
                <StatusBadge value={latestDeployment.status} />
              </div>
              <div className="font-mono text-xs text-muted-foreground">
                {latestDeployment.branch ? `${latestDeployment.branch} · ` : ""}
                {formatRelativeLabel(latestDeployment.created_at)}
              </div>
            </div>
            <Link
              href={`/projects/${id}/deployments`}
              className="shrink-0 rounded-lg border border-border px-3 py-1.5 text-sm transition-colors hover:bg-accent"
            >
              View all deployments
            </Link>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No deployments yet.</p>
        )}
      </Card>

      {/* Quick links */}
      <div className="grid gap-3 sm:grid-cols-2">
        <Link
          href={`/projects/${id}/deployments`}
          className="flex items-center justify-between rounded-xl border border-border bg-muted p-4 text-sm transition-colors hover:border-primary/30 hover:bg-accent"
        >
          <span className="font-medium">Deployments</span>
          <span className="text-muted-foreground">Trigger &amp; view build logs &rarr;</span>
        </Link>
        <Link
          href={`/projects/${id}/env`}
          className="flex items-center justify-between rounded-xl border border-border bg-muted p-4 text-sm transition-colors hover:border-primary/30 hover:bg-accent"
        >
          <span className="font-medium">Environment variables</span>
          <span className="text-muted-foreground">Manage secrets &rarr;</span>
        </Link>
        <Link
          href={`/projects/${id}/domains`}
          className="flex items-center justify-between rounded-xl border border-border bg-muted p-4 text-sm transition-colors hover:border-primary/30 hover:bg-accent"
        >
          <span className="font-medium">Domains</span>
          <span className="text-muted-foreground">Primary domain &amp; DNS &rarr;</span>
        </Link>
        <Link
          href={`/projects/${id}/settings`}
          className="flex items-center justify-between rounded-xl border border-border bg-muted p-4 text-sm transition-colors hover:border-primary/30 hover:bg-accent"
        >
          <span className="font-medium">Settings</span>
          <span className="text-muted-foreground">Deploy &amp; restart actions &rarr;</span>
        </Link>
      </div>
    </div>
  )
}
