import { notFound } from "next/navigation"

import { ProjectActions } from "@/components/projects/project-actions"
import { Card, CardHeader } from "@/components/ui/card"
import { PageHeader } from "@/components/ui/page-header"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { ProjectRecord } from "@/lib/types"

type SettingsPageProps = {
  params: Promise<{ id: string }>
}

export default async function SettingsPage({ params }: SettingsPageProps) {
  const session = await requireConsoleSession()
  const { id } = await params

  const projects = await fetchBackend<ProjectRecord[]>("/projects", {
    token: session.token,
  }).catch(() => [] as ProjectRecord[])

  const project = projects.find((p) => p.id === id)
  if (!project) {
    notFound()
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Configuration"
        title="Settings"
        description="Lifecycle actions and project controls."
      />

      <Card>
        <CardHeader title="Actions" />
        <div className="mt-4">
          <ProjectActions applicationId={id} />
        </div>
      </Card>
    </div>
  )
}
