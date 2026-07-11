import Link from "next/link"

import { SourceBadge } from "@/components/deploys/deployment-card"
import { ProjectActions } from "@/components/projects/project-actions"
import { EmptyState } from "@/components/ui/empty-state"
import { PageHeader, RefreshLink } from "@/components/ui/page-header"
import { StatusBadge } from "@/components/ui/status-badge"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import { unifyNative } from "@/lib/deployments"
import type { DeploymentRecord, ProjectRecord } from "@/lib/types"
import { formatRelativeLabel } from "@/lib/utils"

type ProjectsPageProps = {
  searchParams: Promise<{ refresh?: string }>
}

/**
 * One deployable resource inside a project — a Coolify application/service or a
 * native Tetra-engine deployment group. This is the "deployment" level of
 * tenant > project > deployment.
 */
type Resource = {
  id: string
  name: string
  status: string
  domain: string
  repository: string
  detail: string
  href: string
  linkLabel: string
  applicationId?: string
}

/**
 * A project — the middle tier. For Coolify this mirrors a Coolify *project*
 * (one card holding all its resources, e.g. "Alethia" → Alethia, Alethia NEW,
 * crawl4ai). For the native engine it's a named deployment group.
 */
type UnifiedProject = {
  key: string
  slug: string // URL segment for the project detail page (Coolify only)
  name: string
  source: "coolify" | "git"
  resources: Resource[]
}

const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, "")

export default async function ProjectsPage({ searchParams }: ProjectsPageProps) {
  const session = await requireConsoleSession()
  const params = await searchParams
  const refresh = params.refresh === "1" ? "1" : undefined

  const [coolify, native] = await Promise.all([
    fetchBackend<ProjectRecord[]>("/projects", {
      token: session.token,
      searchParams: { refresh },
    }).catch(() => [] as ProjectRecord[]),
    fetchBackend<DeploymentRecord[]>("/deploys", { token: session.token }).catch(
      () => [] as DeploymentRecord[],
    ),
  ])

  // Group Coolify applications under their owning Coolify project (mirrors
  // Coolify's own project → resources layout). Apps with no project fall back
  // to standing alone under their own name.
  const coolifyGroups = new Map<string, UnifiedProject>()
  for (const p of coolify) {
    const groupKey = p.project_uuid || `name:${norm(p.project_name || p.name)}`
    const projectName = p.project_name || p.name
    const group =
      coolifyGroups.get(groupKey) ??
      ({ key: `coolify:${groupKey}`, slug: groupKey, name: projectName, source: "coolify", resources: [] } as UnifiedProject)
    group.name = p.project_name || group.name
    group.resources.push({
      id: p.id,
      name: p.name,
      status: p.status,
      domain: p.primary_domain,
      repository: p.repository,
      detail: formatRelativeLabel(p.updated_at),
      href: `/projects/${groupKey}/apps/${p.id}`,
      linkLabel: "Open",
      applicationId: p.id,
    })
    coolifyGroups.set(groupKey, group)
  }

  const projects: UnifiedProject[] = [...coolifyGroups.values()]
  const seen = new Set(projects.map((g) => norm(g.name)))

  // Native (Tetra-engine) deployments → one project per project name, its
  // deployments as resources. Skip names already represented by a Coolify project.
  const nativeGroups = new Map<string, DeploymentRecord[]>()
  for (const record of native) {
    const list = nativeGroups.get(record.project) ?? []
    list.push(record)
    nativeGroups.set(record.project, list)
  }
  for (const [name, records] of nativeGroups) {
    if (seen.has(norm(name))) continue
    seen.add(norm(name))
    const latest = records.reduce((a, b) => (a.created_at >= b.created_at ? a : b))
    const unified = unifyNative(latest)
    projects.push({
      key: `native:${name}`,
      slug: `name:${norm(name)}`,
      name,
      source: "git",
      resources: [
        {
          id: name,
          name,
          status: latest.status,
          domain: latest.domain,
          repository: unified.gitUrl ?? "",
          detail: `${records.length} deployment${records.length === 1 ? "" : "s"} · ${formatRelativeLabel(latest.created_at)}`,
          href: "/deploys",
          linkLabel: "View deployments",
        },
      ],
    })
  }

  projects.sort((a, b) => a.name.localeCompare(b.name))

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={session.admin.tenant_name || "Workspace"}
        title="Projects"
        description="Projects hold apps, and each app has its deployments — Coolify projects and Tetra-engine apps in one place."
        action={
          <div className="flex items-center gap-3">
            <RefreshLink href="/projects?refresh=1" label="Refresh" />
            <Link
              href="/deploys"
              className="rounded-lg bg-foreground px-3 py-2 text-sm font-medium text-background transition-colors hover:bg-foreground/90"
            >
              New deployment
            </Link>
          </div>
        }
      />

      <section className="grid gap-4">
        {projects.length > 0 ? (
          projects.map((project) => (
            <article
              key={project.key}
              className="rounded-2xl border border-border bg-card p-5"
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="grid size-10 place-items-center rounded-xl border border-border bg-background font-mono text-sm font-semibold">
                    {project.name.slice(0, 2).toUpperCase()}
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      {project.source === "coolify" ? (
                        <Link
                          href={`/projects/${project.slug}`}
                          className="truncate font-semibold transition-colors hover:text-primary"
                        >
                          {project.name}
                        </Link>
                      ) : (
                        <h2 className="truncate font-semibold">{project.name}</h2>
                      )}
                      <SourceBadge source={project.source} />
                    </div>
                    <div className="font-mono text-xs text-muted-foreground">
                      {project.resources.length} app
                      {project.resources.length === 1 ? "" : "s"}
                    </div>
                  </div>
                </div>
                {project.source === "coolify" ? (
                  <Link
                    href={`/projects/${project.slug}`}
                    className="rounded-lg border border-border px-3 py-1.5 text-sm transition-colors hover:bg-accent"
                  >
                    Open project →
                  </Link>
                ) : null}
              </div>

              {/* Resources / deployments inside this project */}
              <div className="mt-4 divide-y divide-border overflow-hidden rounded-xl border border-border">
                {project.resources.map((res) => (
                  <div
                    key={res.id}
                    className="flex flex-wrap items-center justify-between gap-3 bg-background px-4 py-3"
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="truncate text-sm font-medium">{res.name}</span>
                        <StatusBadge value={res.status} />
                      </div>
                      <div className="mt-0.5 flex flex-wrap gap-x-3 font-mono text-xs text-muted-foreground">
                        {res.domain ? (
                          <a
                            href={`https://${res.domain}`}
                            target="_blank"
                            rel="noreferrer"
                            className="transition-colors hover:text-foreground"
                          >
                            {res.domain}
                          </a>
                        ) : (
                          <span>no domain</span>
                        )}
                        <span className="truncate">{res.repository || "not linked"}</span>
                        <span>{res.detail}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {res.applicationId ? (
                        <ProjectActions applicationId={res.applicationId} />
                      ) : null}
                      <Link
                        href={res.href}
                        className="rounded-lg border border-border px-3 py-1.5 text-sm transition-colors hover:bg-accent"
                      >
                        {res.linkLabel}
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            </article>
          ))
        ) : (
          <EmptyState
            title="No projects yet"
            description="Deploy a git repository or install a marketplace app, or connect Coolify on the backend."
          />
        )}
      </section>
    </div>
  )
}
