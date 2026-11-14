import { DeploysManager } from "@/components/deploys/deploys-manager"
import { DegradedBanner } from "@/components/ui/degraded-banner"
import { PageHeader } from "@/components/ui/page-header"
import { requireConsoleSession } from "@/lib/auth"
import { degradedSources, fetchDegraded } from "@/lib/fetch-degraded"
import type { DeploymentRecord } from "@/lib/types"

/** One app's version history: every build, install and rollback, newest first. */
export default async function AppDeploymentsPage({
  params,
}: {
  params: Promise<{ project: string }>
}) {
  const session = await requireConsoleSession()
  const project = decodeURIComponent((await params).project)
  const deploymentsRes = await fetchDegraded<DeploymentRecord[]>("/deploys", "Deployments", [], {
    token: session.token,
  })
  const deployments = deploymentsRes.data.filter((d) => d.project === project)

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Deployments"
        title={project}
        description="Every build of this app with its logs. Roll back to any earlier image without rebuilding."
      />
      <DegradedBanner sources={degradedSources([deploymentsRes])} />
      <DeploysManager
        deployments={deployments}
        showForm={false}
        emptyDescription="This app has no deployments on record yet."
      />
    </div>
  )
}
