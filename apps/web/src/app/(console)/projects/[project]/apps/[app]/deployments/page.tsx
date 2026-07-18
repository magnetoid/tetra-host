import { notFound } from "next/navigation"

import { DeployConsole } from "@/components/projects/deploy-console"
import { DegradedBanner } from "@/components/ui/degraded-banner"
import { PageHeader } from "@/components/ui/page-header"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import { degradedSources, fetchDegraded } from "@/lib/fetch-degraded"
import type { ProjectDeploymentRecord, ProjectRecord } from "@/lib/types"

type DeploymentsPageProps = {
  params: Promise<{ app: string }>
}

export default async function DeploymentsPage({ params }: DeploymentsPageProps) {
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
    <div className="space-y-6">
      <PageHeader
        eyebrow="Deploy console"
        title="Deployments"
        description="Trigger deploys and watch the build stream in real time."
      />
      <DegradedBanner sources={degradedSources([deploymentsRes])} />
      <DeployConsole applicationId={app} projectName={project.name} initialDeployments={deployments} />
    </div>
  )
}
