import { notFound } from "next/navigation"

import { SetScopeLabels } from "@/components/shell/scope-labels"
import { DegradedBanner } from "@/components/ui/degraded-banner"
import { EmptyState } from "@/components/ui/empty-state"
import { PageHeader } from "@/components/ui/page-header"
import { EnvironmentTabs } from "@/components/workspace/environment-tabs"
import { NewService } from "@/components/workspace/new-service"
import { ServiceList, type ServiceRuntime } from "@/components/workspace/service-list"
import { ApiError, fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import { degradedSources, fetchDegraded } from "@/lib/fetch-degraded"
import type {
  AppTemplate,
  DatabaseEngine,
  DatabaseRecord,
  DeploymentRecord,
  InstalledApp,
  WorkspaceEnvironment,
  WorkspaceProject,
  WorkspaceService,
} from "@/lib/types"
import { teamRef } from "@/lib/workspace"

/** Status, last deploy and engine detail per stack, from the engine listings. */
function runtimeByStack(
  apps: InstalledApp[],
  databases: DatabaseRecord[],
  deployments: DeploymentRecord[],
  services: WorkspaceService[],
): Record<string, ServiceRuntime> {
  const out: Record<string, ServiceRuntime> = {}
  for (const app of apps) out[app.project] = { status: app.status }
  for (const d of deployments) {
    const entry = (out[d.project] ??= {})
    if (!entry.lastDeploy || d.created_at > entry.lastDeploy) entry.lastDeploy = d.created_at
  }
  const dbById = new Map(databases.map((db) => [db.id, db]))
  for (const service of services) {
    const db = service.database_id ? dbById.get(service.database_id) : undefined
    if (db) {
      out[service.external_id] = {
        status: db.status,
        detail: `${db.engine_label} ${db.version} · ${db.host}:${db.port}`,
      }
    }
  }
  return out
}

export default async function EnvironmentPage({
  params,
}: {
  params: Promise<{ project: string; environment: string }>
}) {
  const session = await requireConsoleSession()
  const { project: projectSlug, environment: envSlug } = await params
  const team = teamRef(session.admin)
  const opts = { token: session.token }
  const projectPath = `/teams/${team}/projects/${encodeURIComponent(projectSlug)}`

  let project: WorkspaceProject
  let environments: WorkspaceEnvironment[]
  try {
    ;[project, environments] = await Promise.all([
      fetchBackend<WorkspaceProject>(projectPath, opts),
      fetchBackend<WorkspaceEnvironment[]>(`${projectPath}/environments`, opts),
    ])
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) notFound()
    throw err
  }
  const environment = environments.find((e) => e.slug === envSlug)
  if (!environment) notFound()

  const query = `project=${encodeURIComponent(project.slug)}&environment=${encodeURIComponent(environment.slug)}`
  const [servicesRes, appsRes, databasesRes, deploysRes, catalogRes, enginesRes] = await Promise.all([
    fetchDegraded<WorkspaceService[]>(`/teams/${team}/apps?${query}`, "Services", [], opts),
    fetchDegraded<InstalledApp[]>("/apps", "Apps", [], opts),
    fetchDegraded<DatabaseRecord[]>("/databases", "Databases", [], opts),
    fetchDegraded<DeploymentRecord[]>("/deploys", "Deployments", [], opts),
    fetchDegraded<AppTemplate[]>("/apps/catalog", "Templates", [], opts),
    fetchDegraded<DatabaseEngine[]>("/databases/engines", "Engines", [], opts),
  ])
  const services = servicesRes.data
  const runtime = runtimeByStack(appsRes.data, databasesRes.data, deploysRes.data, services)

  return (
    <div className="space-y-6">
      <SetScopeLabels
        project={project.name}
        projectSlug={project.slug}
        environment={environment.name}
        environmentSlug={environment.slug}
      />
      <PageHeader eyebrow="Project" title={project.name} />
      <EnvironmentTabs team={team} project={project.slug} environments={environments} current={environment.slug} />
      <DegradedBanner
        sources={degradedSources([servicesRes, appsRes, databasesRes, deploysRes, catalogRes, enginesRes])}
      />

      <NewService
        key={environment.id}
        environmentId={environment.id}
        environmentName={environment.name}
        templates={catalogRes.data}
        installedProjects={appsRes.data.map((a) => a.project)}
        engines={enginesRes.data}
        initialOpen={services.length === 0}
      />

      {services.length === 0 ? (
        <EmptyState
          title={`No services in ${environment.name} yet`}
          description="Add a git repository, a template or a database above. Services in one environment reach each other by name on your team's private network."
        />
      ) : (
        <ServiceList services={services} runtime={runtime} />
      )}
    </div>
  )
}
