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
 * A unified project — one card whether it's a Coolify application or a native
 * Tetra-engine project (a group of git/app deployments sharing a name). Same shape,
 * same card; the source badge and detail link are the only things that differ.
 */
type UnifiedProject = {
  key: string
  name: string
  source: "coolify" | "git"
  status: string
  domain: string
  detail: string
  href: string
  deployments: number
  // Coolify-only inline controls (native projects manage from the Deployments feed).
  applicationId?: string
  repository?: string
}

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

  const projects: UnifiedProject[] = coolify.map((p) => ({
    key: `coolify:${p.id}`,
    name: p.name,
    source: "coolify",
    status: p.status,
    domain: p.primary_domain,
    detail: formatRelativeLabel(p.updated_at),
    href: `/projects/${p.id}`,
    deployments: 0,
    applicationId: p.id,
    repository: p.repository,
  }))

  // A project can surface from BOTH Coolify and native deployments — collapse those so it
  // appears once (fixes duplicate "alethia" / "alethia new" style entries).
  const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, "")
  const seen = new Set(coolify.map((p) => norm(p.name)))

  // Group native deployments by project name → one platform project per group.
  const groups = new Map<string, DeploymentRecord[]>()
  for (const record of native) {
    const list = groups.get(record.project) ?? []
    list.push(record)
    groups.set(record.project, list)
  }
  for (const [name, records] of groups) {
    if (seen.has(norm(name))) continue // already represented (Coolify or an earlier group)
    seen.add(norm(name))
    const latest = records.reduce((a, b) => (a.created_at >= b.created_at ? a : b))
    const unified = unifyNative(latest)
    projects.push({
      key: `native:${name}`,
      name,
      source: "git",
      status: latest.status,
      domain: latest.domain,
      detail: `${records.length} deployment${records.length === 1 ? "" : "s"} · ${formatRelativeLabel(latest.created_at)}`,
      href: "/deploys",
      deployments: records.length,
      repository: unified.gitUrl,
    })
  }

  projects.sort((a, b) => a.name.localeCompare(b.name))

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Projects"
        title="Projects"
        description="Every project in one place — Coolify applications and Tetra-engine deployments, unified."
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
              className="card-lift rounded-2xl border border-border bg-card p-5 hover:border-primary/30"
            >
              <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div className="flex items-center gap-3">
                  <div className="grid size-10 place-items-center rounded-xl border border-border bg-background font-mono text-sm font-semibold">
                    {project.name.slice(0, 2).toUpperCase()}
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <h2 className="truncate font-semibold">{project.name}</h2>
                      <SourceBadge source={project.source} />
                    </div>
                    <a
                      className="font-mono text-xs text-muted-foreground transition-colors hover:text-foreground"
                      href={project.domain ? `https://${project.domain}` : undefined}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {project.domain || "no domain"}
                    </a>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <StatusBadge value={project.status} />
                </div>
              </div>

              <div className="mt-5 grid gap-3 text-sm md:grid-cols-3">
                <Field label="Repository" value={project.repository || "Not linked"} mono />
                <Field label="Activity" value={project.detail} />
                <Field
                  label="Source"
                  value={project.source === "coolify" ? "Coolify application" : "Tetra engine"}
                />
              </div>

              <div className="mt-5 flex flex-wrap items-center gap-3">
                {project.applicationId ? <ProjectActions applicationId={project.applicationId} /> : null}
                <Link
                  href={project.href}
                  className="rounded-lg border border-border px-3 py-2 text-sm transition-colors hover:bg-accent"
                >
                  {project.source === "coolify" ? "Open project" : "View deployments"}
                </Link>
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

function Field({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <div className="text-muted-foreground">{label}</div>
      <div className={`mt-1 truncate ${mono ? "font-mono text-xs" : ""}`}>{value}</div>
    </div>
  )
}
