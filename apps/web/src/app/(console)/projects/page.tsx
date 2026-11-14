import { DegradedBanner } from "@/components/ui/degraded-banner"
import { PageHeader } from "@/components/ui/page-header"
import { ProjectsManager } from "@/components/workspace/projects-manager"
import { requireConsoleSession } from "@/lib/auth"
import { degradedSources, fetchDegraded } from "@/lib/fetch-degraded"
import type { WorkspaceProject } from "@/lib/types"
import { teamRef } from "@/lib/workspace"

export default async function ProjectsPage() {
  const session = await requireConsoleSession()
  const team = teamRef(session.admin)
  const projectsRes = await fetchDegraded<WorkspaceProject[]>(
    `/teams/${team}/projects`, "Projects", [], { token: session.token },
  )

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Projects"
        title="Projects"
        description="Each project holds environments (production, staging, previews), and each environment holds its services: apps, templates and databases."
      />
      <DegradedBanner sources={degradedSources([projectsRes])} />
      <ProjectsManager team={team} projects={projectsRes.data} />
    </div>
  )
}
