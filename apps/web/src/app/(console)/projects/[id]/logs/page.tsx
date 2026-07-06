import { notFound } from "next/navigation"

import { DeployConsole } from "@/components/projects/deploy-console"
import { RuntimeLogs } from "@/components/projects/runtime-logs"
import { PageHeader } from "@/components/ui/page-header"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { ProjectDeploymentRecord, ProjectRecord } from "@/lib/types"

type LogsPageProps = {
  params: Promise<{ id: string }>
}

export default async function LogsPage({ params }: LogsPageProps) {
  const session = await requireConsoleSession()
  const { id } = await params

  const [projects, deployments] = await Promise.all([
    fetchBackend<ProjectRecord[]>("/projects", { token: session.token }),
    fetchBackend<ProjectDeploymentRecord[]>(`/projects/${id}/deployments`, {
      token: session.token,
    }).catch(() => [] as ProjectDeploymentRecord[]),
  ])

  const project = projects.find((p) => p.id === id)
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

      <section className="space-y-3">
        <div>
          <h2 className="text-lg font-semibold">Runtime</h2>
          <p className="text-sm text-muted-foreground">Live output from the running container.</p>
        </div>
        <RuntimeLogs projectId={id} />
      </section>

      <section className="space-y-3">
        <div>
          <h2 className="text-lg font-semibold">Build logs</h2>
          <p className="text-sm text-muted-foreground">Select a deployment to stream its build output.</p>
        </div>
        <DeployConsole applicationId={id} initialDeployments={deployments} />
      </section>
    </div>
  )
}
