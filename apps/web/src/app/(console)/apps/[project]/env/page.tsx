import Link from "next/link"

import { EnvManager } from "@/components/env/env-manager"
import { DegradedBanner } from "@/components/ui/degraded-banner"
import { PageHeader } from "@/components/ui/page-header"
import { requireConsoleSession } from "@/lib/auth"
import { degradedSources, fetchDegraded } from "@/lib/fetch-degraded"
import type { AppEnvVar } from "@/lib/types"

export default async function AppEnvPage({
  params,
}: {
  params: Promise<{ project: string }>
}) {
  const session = await requireConsoleSession()
  const { project } = await params

  const varsRes = await fetchDegraded<AppEnvVar[]>(`/deploys/${project}/env`, "Env vars", [], {
    token: session.token,
  })
  const vars = varsRes.data

  return (
    <div className="space-y-6">
      <Link href="/apps" className="text-sm text-muted-foreground hover:text-foreground">
        ← Apps
      </Link>
      <PageHeader
        eyebrow="Environment"
        title={project}
        description="Variables injected into this app's containers — secrets are encrypted at rest."
      />
      <DegradedBanner sources={degradedSources([varsRes])} />
      <EnvManager target={{ kind: "deploy", project }} vars={vars} />
    </div>
  )
}
