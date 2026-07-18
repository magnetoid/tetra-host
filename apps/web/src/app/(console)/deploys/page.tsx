import { DeployHooksManager } from "@/components/deploys/deploy-hooks-manager"
import { DeploysManager } from "@/components/deploys/deploys-manager"
import { PreviewsManager } from "@/components/deploys/previews-manager"
import { Card, CardHeader } from "@/components/ui/card"
import { DegradedBanner } from "@/components/ui/degraded-banner"
import { PageHeader } from "@/components/ui/page-header"
import { requireConsoleSession } from "@/lib/auth"
import { degradedSources, fetchDegraded } from "@/lib/fetch-degraded"
import type { DeployHook, DeploymentRecord, PreviewRecord } from "@/lib/types"

export default async function DeploysPage() {
  const session = await requireConsoleSession()
  const [deploymentsRes, hooksRes, previewsRes] = await Promise.all([
    fetchDegraded<DeploymentRecord[]>("/deploys", "Deployments", [], { token: session.token }),
    fetchDegraded<DeployHook[]>("/deploy-hooks", "Deploy hooks", [], { token: session.token }),
    fetchDegraded<PreviewRecord[]>("/previews", "Previews", [], { token: session.token }),
  ])
  const deployments = deploymentsRes.data
  const hooks = hooksRes.data
  const previews = previewsRes.data

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Deployments"
        title="All deployments"
        description="Every deployment across your projects — build and run any git repository, live build logs, instant rollback."
      />
      <DegradedBanner sources={degradedSources([deploymentsRes, hooksRes, previewsRes])} />
      <DeploysManager deployments={deployments} />
      <Card>
        <CardHeader title="Preview environments" action="one URL per branch" />
        <div className="mt-4">
          <PreviewsManager previews={previews} />
        </div>
      </Card>
      <Card>
        <CardHeader title="Push-to-deploy" action="GitHub webhooks" />
        <div className="mt-4">
          <DeployHooksManager hooks={hooks} />
        </div>
      </Card>
    </div>
  )
}
