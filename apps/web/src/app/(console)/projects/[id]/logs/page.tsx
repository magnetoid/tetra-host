import { notFound } from "next/navigation"

import { DeployConsole } from "@/components/projects/deploy-console"
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
    <div className="space-y-6">
      <PageHeader
        eyebrow="Build output"
        title="Logs"
        description="Select a deployment to stream its build logs."
      />
      <DeployConsole applicationId={id} initialDeployments={deployments} />
    </div>
  )
}
