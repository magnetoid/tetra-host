import Link from "next/link"

import { ComputePanel } from "@/components/apps/compute-panel"
import { DegradedBanner } from "@/components/ui/degraded-banner"
import { PageHeader } from "@/components/ui/page-header"
import { requireConsoleSession } from "@/lib/auth"
import { degradedSources, fetchDegraded } from "@/lib/fetch-degraded"
import type { ComputeMetrics } from "@/lib/types"

export default async function AppComputePage({
  params,
}: {
  params: Promise<{ project: string }>
}) {
  const session = await requireConsoleSession()
  const { project } = await params

  const initialRes = await fetchDegraded<ComputeMetrics | null>(
    `/apps/${project}/compute`,
    "Compute",
    null,
    { token: session.token },
  )
  const initial = initialRes.data

  return (
    <div className="space-y-6">
      <Link href="/apps" className="text-sm text-muted-foreground hover:text-foreground">
        ← Apps
      </Link>
      <PageHeader
        eyebrow="Compute"
        title={project}
        description="Live CPU, memory, and network usage for this app's containers."
      />
      <DegradedBanner sources={degradedSources([initialRes])} />
      <ComputePanel project={project} initial={initial} />
    </div>
  )
}
