import { notFound } from "next/navigation"

import { EnvManager, type EnvVar } from "@/components/projects/env-manager"
import { PageHeader } from "@/components/ui/page-header"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { ProjectRecord } from "@/lib/types"

type EnvPageProps = {
  params: Promise<{ app: string }>
}

export default async function EnvPage({ params }: EnvPageProps) {
  const session = await requireConsoleSession()
  const { app } = await params

  const [projects, envs] = await Promise.all([
    fetchBackend<ProjectRecord[]>("/projects", { token: session.token }),
    fetchBackend<EnvVar[]>(`/projects/${app}/envs`, { token: session.token }).catch(
      () => [] as EnvVar[],
    ),
  ])

  const project = projects.find((p) => p.id === app)
  if (!project) {
    notFound()
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Configuration"
        title="Environment variables"
        description="Manage secrets and runtime configuration for this app."
      />
      <EnvManager applicationId={app} initialEnvs={envs} />
    </div>
  )
}
