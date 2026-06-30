import Link from "next/link"
import { notFound } from "next/navigation"

import { DeployConsole } from "@/components/projects/deploy-console"
import { EnvManager, type EnvVar } from "@/components/projects/env-manager"
import { PageHeader } from "@/components/ui/page-header"
import { StatusBadge } from "@/components/ui/status-badge"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { ProjectDeploymentRecord, ProjectRecord } from "@/lib/types"

type ProjectDetailPageProps = {
  params: Promise<{ id: string }>
}

export default async function ProjectDetailPage({ params }: ProjectDetailPageProps) {
  const session = await requireConsoleSession()
  const { id } = await params

  const [projects, deployments, envs] = await Promise.all([
    fetchBackend<ProjectRecord[]>("/projects", { token: session.token }),
    fetchBackend<ProjectDeploymentRecord[]>(`/projects/${id}/deployments`, {
      token: session.token,
    }).catch(() => [] as ProjectDeploymentRecord[]),
    fetchBackend<EnvVar[]>(`/projects/${id}/envs`, { token: session.token }).catch(
      () => [] as EnvVar[],
    ),
  ])

  const project = projects.find((item) => item.id === id)
  if (!project) {
    notFound()
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Coolify deploy console"
        title={project.name}
        description="Trigger deploys and watch the build stream in real time."
        action={
          <Link
            href="/projects"
            className="inline-flex rounded-lg border border-border px-4 py-2 text-sm text-zinc-300 transition hover:bg-zinc-900"
          >
            Back to projects
          </Link>
        }
      />

      <div className="flex flex-wrap items-center gap-2 text-sm">
        <StatusBadge value={project.environment || "Production"} />
        <StatusBadge value={project.status} />
        <a
          className="text-zinc-400 hover:text-zinc-200"
          href={`https://${project.primary_domain}`}
          target="_blank"
          rel="noreferrer"
        >
          {project.primary_domain}
        </a>
        {project.repository ? <span className="text-zinc-600">· {project.repository}</span> : null}
      </div>

      <DeployConsole applicationId={project.id} initialDeployments={deployments} />

      <EnvManager applicationId={project.id} initialEnvs={envs} />
    </div>
  )
}
