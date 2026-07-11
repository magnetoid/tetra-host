import Link from "next/link"
import { notFound } from "next/navigation"

import { ProjectActions } from "@/components/projects/project-actions"
import { PageHeader, RefreshLink } from "@/components/ui/page-header"
import { StatusBadge } from "@/components/ui/status-badge"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import { projectSlug } from "@/lib/projects"
import type { ProjectRecord } from "@/lib/types"
import { formatRelativeLabel } from "@/lib/utils"

type ProjectPageProps = {
  params: Promise<{ project: string }>
  searchParams: Promise<{ refresh?: string }>
}

/**
 * Project detail — the middle tier of tenant > project > app > deployment.
 * Lists every app inside one Coolify project; each app drills into its own
 * deployments/logs/env/… surface.
 */
export default async function ProjectPage({ params, searchParams }: ProjectPageProps) {
  const session = await requireConsoleSession()
  const { project: slug } = await params
  const { refresh } = await searchParams

  const records = await fetchBackend<ProjectRecord[]>("/projects", {
    token: session.token,
    searchParams: { refresh: refresh === "1" ? "1" : undefined },
  }).catch(() => [] as ProjectRecord[])

  const apps = records.filter((p) => projectSlug(p) === decodeURIComponent(slug))
  if (apps.length === 0) {
    notFound()
  }

  const projectName = apps[0].project_name || apps[0].name

  return (
    <div className="space-y-6">
      <Link
        href="/projects"
        className="inline-flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <span aria-hidden>←</span> All projects
      </Link>

      <PageHeader
        eyebrow={session.admin.tenant_name ? `${session.admin.tenant_name} › Project` : "Project"}
        title={projectName}
        description={`${apps.length} app${apps.length === 1 ? "" : "s"} in this project — open one to manage its deployments, logs, and settings.`}
        action={<RefreshLink href={`/projects/${slug}?refresh=1`} label="Refresh" />}
      />

      <section className="grid gap-4 sm:grid-cols-2">
        {apps.map((app) => (
          <article key={app.id} className="flex flex-col rounded-2xl border border-border bg-card p-5">
            <div className="flex items-start justify-between gap-3">
              <div className="flex min-w-0 items-center gap-3">
                <div className="grid size-10 shrink-0 place-items-center rounded-xl border border-border bg-background font-mono text-sm font-semibold">
                  {app.name.slice(0, 2).toUpperCase()}
                </div>
                <div className="min-w-0">
                  <h2 className="truncate font-semibold">{app.name}</h2>
                  <div className="font-mono text-xs text-muted-foreground">
                    {app.repository || "not linked"}
                  </div>
                </div>
              </div>
              <StatusBadge value={app.status} />
            </div>

            <div className="mt-4 flex flex-wrap gap-x-3 gap-y-1 font-mono text-xs text-muted-foreground">
              {app.primary_domain ? (
                <a
                  href={`https://${app.primary_domain}`}
                  target="_blank"
                  rel="noreferrer"
                  className="transition-colors hover:text-foreground"
                >
                  {app.primary_domain}
                </a>
              ) : (
                <span>no domain</span>
              )}
              <span>{formatRelativeLabel(app.updated_at)}</span>
            </div>

            <div className="mt-4 flex items-center gap-2 border-t border-border pt-4">
              <ProjectActions applicationId={app.id} />
              <Link
                href={`/projects/${slug}/apps/${app.id}`}
                className="ml-auto rounded-lg bg-foreground px-3 py-1.5 text-sm font-medium text-background transition-colors hover:bg-foreground/90"
              >
                Open app →
              </Link>
            </div>
          </article>
        ))}
      </section>
    </div>
  )
}
