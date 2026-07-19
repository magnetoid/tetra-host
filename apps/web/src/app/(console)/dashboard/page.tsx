import Link from "next/link"

import { AppStatus } from "@/components/ui/app-status"
import { Card } from "@/components/ui/card"
import { DegradedBanner } from "@/components/ui/degraded-banner"
import { EmptyState } from "@/components/ui/empty-state"
import { PageHeader, RefreshLink } from "@/components/ui/page-header"
import { StatCard } from "@/components/ui/stat-card"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import { degradedSources, fetchDegraded } from "@/lib/fetch-degraded"
import { faEnvelope, faGlobe, faServer, faTriangleExclamation } from "@/lib/icons"
import type { DashboardResponse, DNSResponse, MailResponse, ProjectRecord } from "@/lib/types"

const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, "")

// A project groups one-or-more deployable apps (mirrors Coolify's project →
// resources). We group the flat app list into projects for the portfolio grid.
type ProjectGroup = {
  slug: string
  name: string
  apps: ProjectRecord[]
  domain: string
  unhealthy: boolean
}

function groupProjects(apps: ProjectRecord[]): ProjectGroup[] {
  const groups = new Map<string, ProjectGroup>()
  for (const app of apps) {
    const slug = app.project_uuid || `name:${norm(app.project_name || app.name)}`
    const name = app.project_name || app.name
    const group =
      groups.get(slug) ??
      ({ slug, name, apps: [], domain: "", unhealthy: false } as ProjectGroup)
    group.apps.push(app)
    if (!group.domain && app.primary_domain) group.domain = app.primary_domain
    if (app.status && !["running", "healthy", "active"].includes(app.status.toLowerCase())) {
      group.unhealthy = true
    }
    groups.set(slug, group)
  }
  return [...groups.values()].sort((a, b) => a.name.localeCompare(b.name))
}

/**
 * Console Overview — the "All projects" view. When a specific project is chosen
 * in the sidebar selector the console routes to that project's own overview
 * (/projects/<slug>); here, with "All projects" selected, it shows the whole
 * portfolio plus a light read on mail/DNS. Operator-level provider health and
 * traffic live on Super Admin, not here.
 */
export default async function DashboardPage() {
  const session = await requireConsoleSession()
  const dashboard = await fetchBackend<DashboardResponse>("/dashboard", { token: session.token })
  const [projectsRes, mailRes, dnsRes] = await Promise.all([
    fetchDegraded<ProjectRecord[]>("/projects", "Projects", [], { token: session.token }),
    fetchDegraded<MailResponse>(
      "/mail",
      "Mail",
      { providers: [], domains: [], mailboxes: [] },
      { token: session.token },
    ),
    fetchDegraded<DNSResponse>(
      "/dns",
      "DNS",
      { providers: [], selected_zone: "", zones: [], records: [] },
      { token: session.token },
    ),
  ])
  const projects = groupProjects(projectsRes.data)
  const mail = mailRes.data
  const dns = dnsRes.data
  const degraded = degradedSources([projectsRes, mailRes, dnsRes])

  const m = dashboard.metrics

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={session.admin.tenant_name ?? "Workspace"}
        title="Overview"
        description="Every project in your workspace, with mail and DNS at a glance."
        action={
          <div className="flex gap-2">
            <RefreshLink href="/dashboard" label="Refresh" />
            {session.admin.role === "platform_admin" ? (
              <Link
                href="/super-admin"
                className="rounded-lg border border-border px-4 py-2 text-sm font-medium transition hover:bg-accent"
              >
                Super Admin
              </Link>
            ) : null}
          </div>
        }
      />

      <DegradedBanner sources={degraded} />

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard icon={faServer} label="Projects" value={projects.length} hint={session.admin.tenant_name ?? "Your workspace"} accent="text-primary" />
        <StatCard
          icon={faTriangleExclamation}
          label="Unhealthy"
          value={m.unhealthy_projects}
          hint={m.unhealthy_projects > 0 ? "Need attention" : "All healthy"}
          accent={m.unhealthy_projects > 0 ? "text-status-err" : "text-muted-foreground"}
        />
        <StatCard icon={faEnvelope} label="Mail domains" value={m.mail_domains} hint="Mailcow" accent="text-muted-foreground" />
        <StatCard icon={faGlobe} label="DNS zones" value={m.dns_zones} hint="Cloudflare" accent="text-muted-foreground" />
      </section>

      {/* All projects — the portfolio grid. */}
      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Projects</h2>
          <Link href="/projects" className="text-sm text-muted-foreground transition hover:text-foreground">
            Manage all →
          </Link>
        </div>
        {projects.length === 0 ? (
          <EmptyState
            title="No projects yet"
            description="Deploy from a Git repo or the app catalog to see your projects here."
            action={
              <Link
                href="/projects"
                className="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-1.5 text-sm font-medium transition-colors hover:border-primary/40 hover:bg-accent"
              >
                Create your first project →
              </Link>
            }
          />
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {projects.map((project) => (
              <Link
                key={project.slug}
                href={`/projects/${project.slug}`}
                className="group flex flex-col gap-2 rounded-lg border border-border bg-card p-4 shadow-sm transition-colors hover:border-primary/40 hover:bg-accent"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate font-medium">{project.name}</span>
                  <AppStatus value={project.unhealthy ? "unhealthy" : "running"} />
                </div>
                <div className="truncate font-mono text-xs text-muted-foreground">
                  {project.domain || "no domain yet"}
                </div>
                <div className="mt-1 text-xs text-muted-foreground">
                  {project.apps.length} app{project.apps.length === 1 ? "" : "s"}
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>

      {/* Secondary resource previews. */}
      <section className="grid gap-4 lg:grid-cols-2">
        <PreviewPanel title="Mail domains" href="/mail" empty="No mail domains yet.">
          {mail.domains.slice(0, 4).map((domain) => (
            <PreviewItem
              key={domain.domain_name}
              title={domain.domain_name}
              subtitle={`${domain.mailboxes} mailboxes · ${domain.aliases} aliases`}
              mono
            />
          ))}
        </PreviewPanel>
        <PreviewPanel title="DNS zones" href="/dns" empty="No DNS zones yet.">
          {dns.zones.slice(0, 4).map((zone) => (
            <PreviewItem
              key={zone.id}
              title={zone.name}
              subtitle={[zone.status, zone.account_name].filter(Boolean).join(" · ")}
              mono
            />
          ))}
        </PreviewPanel>
      </section>
    </div>
  )
}

function PreviewPanel({
  title,
  href,
  empty,
  children,
}: {
  title: string
  href: string
  empty: string
  children: React.ReactNode
}) {
  const items = Array.isArray(children) ? children : [children]
  const hasItems = items.some(Boolean)

  return (
    <Card>
      <div className="flex items-center justify-between">
        <h2 className="font-display text-lg font-semibold">{title}</h2>
        <Link href={href} className="text-sm text-muted-foreground transition hover:text-foreground">
          View all
        </Link>
      </div>
      <div className="mt-4 space-y-3">
        {hasItems ? (
          children
        ) : (
          <div className="rounded-lg border border-dashed border-border bg-background p-4 text-sm text-muted-foreground">
            {empty}
          </div>
        )}
      </div>
    </Card>
  )
}

function PreviewItem({
  title,
  subtitle,
  mono = false,
}: {
  title: string
  subtitle: string
  mono?: boolean
}) {
  return (
    <div className="rounded-lg border border-border bg-background p-4 transition-colors hover:border-primary/30">
      <div className="font-medium">{title}</div>
      <div className={`mt-1 text-sm text-muted-foreground ${mono ? "font-mono text-xs" : ""}`}>
        {subtitle || "—"}
      </div>
    </div>
  )
}
