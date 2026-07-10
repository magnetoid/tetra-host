import { DeployHooksManager } from "@/components/deploys/deploy-hooks-manager"
import { DeploysManager } from "@/components/deploys/deploys-manager"
import { PreviewsManager } from "@/components/deploys/previews-manager"
import { Card, CardHeader } from "@/components/ui/card"
import { PageHeader } from "@/components/ui/page-header"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { DeployHook, DeploymentRecord, PreviewRecord } from "@/lib/types"

export default async function DeploysPage() {
  const session = await requireConsoleSession()
  const [deployments, hooks, previews] = await Promise.all([
    fetchBackend<DeploymentRecord[]>("/deploys", { token: session.token }).catch(() => []),
    fetchBackend<DeployHook[]>("/deploy-hooks", { token: session.token }).catch(() => []),
    fetchBackend<PreviewRecord[]>("/previews", { token: session.token }).catch(() => []),
  ])

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Deployments"
        title="All deployments"
        description="Every deployment across your projects — build and run any git repository, live build logs, instant rollback."
      />
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
