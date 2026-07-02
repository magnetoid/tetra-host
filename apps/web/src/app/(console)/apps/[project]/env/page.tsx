import Link from "next/link"

import { EnvManager } from "@/components/apps/env-manager"
import { PageHeader } from "@/components/ui/page-header"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { AppEnvVar } from "@/lib/types"

export default async function AppEnvPage({
  params,
}: {
  params: Promise<{ project: string }>
}) {
  const session = await requireConsoleSession()
  const { project } = await params

  const vars = await fetchBackend<AppEnvVar[]>(`/deploys/${project}/env`, {
    token: session.token,
  }).catch(() => [])

  return (
    <div className="space-y-6">
      <Link href="/apps" className="text-sm text-zinc-500 hover:text-zinc-300">
        ← Apps
      </Link>
      <PageHeader
        eyebrow="Environment"
        title={project}
        description="Variables injected into this app's containers — secrets are encrypted at rest."
      />
      <EnvManager project={project} vars={vars} />
    </div>
  )
}
