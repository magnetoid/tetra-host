import { notFound } from "next/navigation"

import { EnvManager, type EnvRow } from "@/components/env/env-manager"
import { DegradedBanner } from "@/components/ui/degraded-banner"
import { PageHeader } from "@/components/ui/page-header"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import { degradedSources, fetchDegraded } from "@/lib/fetch-degraded"
import type { ProjectRecord } from "@/lib/types"

type EnvPageProps = {
  params: Promise<{ app: string }>
}

export default async function EnvPage({ params }: EnvPageProps) {
  const session = await requireConsoleSession()
  const { app } = await params

  const [projects, envsRes] = await Promise.all([
    fetchBackend<ProjectRecord[]>("/projects", { token: session.token }),
    fetchDegraded<EnvRow[]>(`/projects/${app}/envs`, "Env vars", [], { token: session.token }),
  ])
  const envs = envsRes.data

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
      <DegradedBanner sources={degradedSources([envsRes])} />
      <EnvManager target={{ kind: "app", applicationId: app }} vars={envs} />
    </div>
  )
}
