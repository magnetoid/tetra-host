import { notFound } from "next/navigation"

import { DeployConsole } from "@/components/projects/deploy-console"
import { RuntimeLogs } from "@/components/projects/runtime-logs"
import { DegradedBanner } from "@/components/ui/degraded-banner"
import { PageHeader } from "@/components/ui/page-header"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import { degradedSources, fetchDegraded } from "@/lib/fetch-degraded"
import type { ProjectDeploymentRecord, ProjectRecord } from "@/lib/types"

type LogsPageProps = {
  params: Promise<{ app: string }>
}

export default async function LogsPage({ params }: LogsPageProps) {
  const session = await requireConsoleSession()
  const { app } = await params

  const [projects, deploymentsRes] = await Promise.all([
    fetchBackend<ProjectRecord[]>("/projects", { token: session.token }),
    fetchDegraded<ProjectDeploymentRecord[]>(`/projects/${app}/deployments`, "Deployments", [], {
      token: session.token,
    }),
  ])
  const deployments = deploymentsRes.data

  const project = projects.find((p) => p.id === app)
  if (!project) {
    notFound()
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Observability"
        title="Logs"
        description="Live runtime output from the running container, plus per-deployment build logs."
      />
      <DegradedBanner sources={degradedSources([deploymentsRes])} />

      <section className="space-y-3">
        <div>
          <h2 className="text-lg font-semibold">Runtime</h2>
          <p className="text-sm text-muted-foreground">Live output from the running container.</p>
        </div>
        <RuntimeLogs projectId={app} />
      </section>

      <section className="space-y-3">
        <div>
          <h2 className="text-lg font-semibold">Build logs</h2>
          <p className="text-sm text-muted-foreground">Select a deployment to stream its build output.</p>
        </div>
        <DeployConsole applicationId={app} initialDeployments={deployments} />
      </section>
    </div>
  )
}
