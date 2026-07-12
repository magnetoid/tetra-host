import { notFound } from "next/navigation"

import { EditAppForm } from "@/components/projects/edit-app-form"
import { ProjectActions } from "@/components/projects/project-actions"
import { Card, CardHeader } from "@/components/ui/card"
import { PageHeader } from "@/components/ui/page-header"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { ProjectRecord } from "@/lib/types"

type SettingsPageProps = {
  params: Promise<{ app: string }>
}

export default async function SettingsPage({ params }: SettingsPageProps) {
  const session = await requireConsoleSession()
  const { app } = await params

  const projects = await fetchBackend<ProjectRecord[]>("/projects", {
    token: session.token,
  }).catch(() => [] as ProjectRecord[])

  const project = projects.find((p) => p.id === app)
  if (!project) {
    notFound()
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Configuration"
        title="Settings"
        description="Edit this app's identity and build settings, or run lifecycle actions."
      />

      <Card>
        <CardHeader title="Edit app" />
        <div className="mt-4">
          <EditAppForm app={project} />
        </div>
      </Card>

      <Card>
        <CardHeader title="Actions" />
        <div className="mt-4">
          <ProjectActions applicationId={app} />
        </div>
      </Card>
    </div>
  )
}
