import { notFound } from "next/navigation"

import { EnvManager, type EnvVar } from "@/components/projects/env-manager"
import { PageHeader } from "@/components/ui/page-header"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { ProjectRecord } from "@/lib/types"

type EnvPageProps = {
  params: Promise<{ id: string }>
}

export default async function EnvPage({ params }: EnvPageProps) {
  const session = await requireConsoleSession()
  const { id } = await params

  const [projects, envs] = await Promise.all([
    fetchBackend<ProjectRecord[]>("/projects", { token: session.token }),
    fetchBackend<EnvVar[]>(`/projects/${id}/envs`, { token: session.token }).catch(
      () => [] as EnvVar[],
    ),
  ])

  const project = projects.find((p) => p.id === id)
  if (!project) {
    notFound()
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Configuration"
        title="Environment variables"
        description="Manage secrets and runtime configuration for this project."
      />
      <EnvManager applicationId={id} initialEnvs={envs} />
    </div>
  )
}
