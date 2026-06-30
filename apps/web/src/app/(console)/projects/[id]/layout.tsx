import { notFound } from "next/navigation"

import { ProjectSubNav } from "@/components/projects/project-sub-nav"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { ProjectRecord } from "@/lib/types"

type ProjectLayoutProps = {
  children: React.ReactNode
  params: Promise<{ id: string }>
}

export default async function ProjectLayout({ children, params }: ProjectLayoutProps) {
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
    <div className="flex min-h-0 gap-8">
      <div className="w-48 shrink-0">
        <ProjectSubNav projectId={id} projectName={project.name} />
      </div>
      <main className="min-w-0 flex-1">{children}</main>
    </div>
  )
}
