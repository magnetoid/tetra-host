import { DeployHooksManager } from "@/components/deploys/deploy-hooks-manager"
import { DeploysManager } from "@/components/deploys/deploys-manager"
import { Card, CardHeader } from "@/components/ui/card"
import { PageHeader } from "@/components/ui/page-header"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { DeployHook, DeploymentRecord } from "@/lib/types"

export default async function DeploysPage() {
  const session = await requireConsoleSession()
  const [deployments, hooks] = await Promise.all([
    fetchBackend<DeploymentRecord[]>("/deploys", { token: session.token }).catch(() => []),
    fetchBackend<DeployHook[]>("/deploy-hooks", { token: session.token }).catch(() => []),
  ])

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Tetra Engine"
        title="Deploys"
        description="Build and run any git repository — live build logs, instant rollback."
      />
      <DeploysManager deployments={deployments} />
      <Card>
        <CardHeader title="Push-to-deploy" action="GitHub webhooks" />
        <div className="mt-4">
          <DeployHooksManager hooks={hooks} />
        </div>
      </Card>
    </div>
  )
}
