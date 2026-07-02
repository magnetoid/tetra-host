import { DeploysManager } from "@/components/deploys/deploys-manager"
import { PageHeader } from "@/components/ui/page-header"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { DeploymentRecord } from "@/lib/types"

export default async function DeploysPage() {
  const session = await requireConsoleSession()
  const deployments = await fetchBackend<DeploymentRecord[]>("/deploys", {
    token: session.token,
  }).catch(() => [])

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Tetra Engine"
        title="Deploys"
        description="Build and run any git repository — live build logs, instant rollback."
      />
      <DeploysManager deployments={deployments} />
    </div>
  )
}
