import Link from "next/link"

import { ProjectActions } from "@/components/projects/project-actions"
import { Card } from "@/components/ui/card"
import { EmptyState } from "@/components/ui/empty-state"
import { PageHeader, RefreshLink } from "@/components/ui/page-header"
import { StatusBadge } from "@/components/ui/status-badge"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { ProjectDeploymentRecord, ProjectRecord } from "@/lib/types"
import { formatRelativeLabel } from "@/lib/utils"

type ProjectsPageProps = {
  searchParams: Promise<{ refresh?: string; app?: string }>
}

export default async function ProjectsPage({ searchParams }: ProjectsPageProps) {
  const session = await requireConsoleSession()
  const params = await searchParams
  const refresh = params.refresh === "1" ? "1" : undefined
  const projects = await fetchBackend<ProjectRecord[]>("/projects", {
    token: session.token,
    searchParams: { refresh },
  })

  let deployments: ProjectDeploymentRecord[] = []
  if (params.app) {
    deployments = await fetchBackend<ProjectDeploymentRecord[]>(
      `/projects/${params.app}/deployments`,
      { token: session.token },
    ).catch(() => [])
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Coolify backend"
        title="Projects"
        description="Operational inventory of Coolify applications with deployment-safe controls."
        action={<RefreshLink href="/projects?refresh=1" label="Refresh inventory" />}
      />

      <section className="grid gap-4">
        {projects.length > 0 ? (
          projects.map((project) => (
            <article
              key={project.id}
              className="rounded-2xl border border-border bg-card p-5 transition-colors hover:border-primary/30"
            >
              <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div className="flex items-center gap-3">
                  <div className="grid size-10 place-items-center rounded-xl border border-border bg-background font-mono text-sm font-semibold">
                    {project.name.slice(0, 2).toUpperCase()}
                  </div>
                  <div>
                    <h2 className="font-semibold">{project.name}</h2>
                    <a
                      className="font-mono text-xs text-muted-foreground transition-colors hover:text-foreground"
                      href={`https://${project.primary_domain}`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {project.primary_domain || "no domain"}
                    </a>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <StatusBadge value={project.environment || "Production"} />
                  <StatusBadge value={project.status} />
                </div>
              </div>

              <div className="mt-5 grid gap-3 text-sm md:grid-cols-4">
                <Field label="Repository" value={project.repository || "Not linked"} mono />
                <Field label="Environment" value={project.environment || "Production"} />
                <Field label="Last update" value={formatRelativeLabel(project.updated_at)} />
                <Field
                  label="Health checks"
                  value={project.healthcheck_enabled ? "Enabled" : "Unavailable"}
                />
              </div>

              <div className="mt-5 flex flex-wrap items-center gap-3">
                <ProjectActions applicationId={project.id} />
                <Link
                  href={`/projects/${project.id}`}
                  className="rounded-lg border border-border px-3 py-2 text-sm transition-colors hover:bg-accent"
                >
                  Open deploy console
                </Link>
              </div>
            </article>
          ))
        ) : (
          <EmptyState
            title="No applications were returned from Coolify."
            description="Connect COOLIFY_URL and COOLIFY_TOKEN on the backend to load production data."
          />
        )}
      </section>

      {params.app ? (
        <Card>
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="font-display text-lg font-semibold">Recent deployments</h2>
              <p className="mt-1 font-mono text-xs text-muted-foreground">{params.app}</p>
            </div>
            <Link
              href="/projects"
              className="text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              Clear
            </Link>
          </div>
          <div className="mt-4 space-y-3 text-sm">
            {deployments.length > 0 ? (
              deployments.map((deployment) => (
                <div key={deployment.id} className="rounded-xl border border-border bg-background p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-mono text-xs">{deployment.id}</div>
                    <StatusBadge value={deployment.status} />
                  </div>
                  <div className="mt-2 font-mono text-xs text-muted-foreground">
                    {deployment.branch || "n/a"} · {deployment.commit || "n/a"} ·{" "}
                    {formatRelativeLabel(deployment.created_at)}
                  </div>
                </div>
              ))
            ) : (
              <div className="text-muted-foreground">No deployments found for this application.</div>
            )}
          </div>
        </Card>
      ) : null}
    </div>
  )
}

function Field({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <div className="text-muted-foreground">{label}</div>
      <div className={`mt-1 truncate ${mono ? "font-mono text-xs" : ""}`}>{value}</div>
    </div>
  )
}
