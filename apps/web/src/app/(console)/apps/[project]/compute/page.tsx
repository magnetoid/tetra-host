import Link from "next/link"

import { ComputePanel } from "@/components/apps/compute-panel"
import { PageHeader } from "@/components/ui/page-header"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { ComputeMetrics } from "@/lib/types"

export default async function AppComputePage({
  params,
}: {
  params: Promise<{ project: string }>
}) {
  const session = await requireConsoleSession()
  const { project } = await params

  const initial = await fetchBackend<ComputeMetrics>(`/apps/${project}/compute`, {
    token: session.token,
  }).catch(() => null)

  return (
    <div className="space-y-6">
      <Link href="/apps" className="text-sm text-zinc-500 hover:text-zinc-300">
        ← Apps
      </Link>
      <PageHeader
        eyebrow="Compute"
        title={project}
        description="Live CPU, memory, and network usage for this app's containers."
      />
      <ComputePanel project={project} initial={initial} />
    </div>
  )
}
