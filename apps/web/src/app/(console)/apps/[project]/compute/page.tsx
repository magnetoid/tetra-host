import { AppControls } from "@/components/apps/app-controls"
import { AppVolumes } from "@/components/apps/app-volumes"
import { ComputePanel } from "@/components/apps/compute-panel"
import { DegradedBanner } from "@/components/ui/degraded-banner"
import { PageHeader } from "@/components/ui/page-header"
import { requireConsoleSession } from "@/lib/auth"
import { degradedSources, fetchDegraded } from "@/lib/fetch-degraded"
import type { AppVolumes as AppVolumesData, ComputeMetrics } from "@/lib/types"

export default async function AppComputePage({
  params,
}: {
  params: Promise<{ project: string }>
}) {
  const session = await requireConsoleSession()
  const { project } = await params

  const [initialRes, volumesRes] = await Promise.all([
    fetchDegraded<ComputeMetrics | null>(`/apps/${project}/compute`, "Compute", null, {
      token: session.token,
    }),
    fetchDegraded<AppVolumesData>(
      `/apps/${project}/volumes`,
      "Volumes",
      { project, mounts: [] },
      { token: session.token },
    ),
  ])
  const initial = initialRes.data

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Compute"
        title={project}
        description="Live CPU, memory, and network usage for this app's containers."
        action={<AppControls project={project} />}
      />
      <DegradedBanner sources={degradedSources([initialRes, volumesRes])} />
      <ComputePanel project={project} initial={initial} />
      <AppVolumes mounts={volumesRes.data.mounts} />
    </div>
  )
}
