import { notFound } from "next/navigation"

import { ProjectSubNav } from "@/components/projects/project-sub-nav"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { ProjectRecord } from "@/lib/types"

type AppLayoutProps = {
  children: React.ReactNode
  params: Promise<{ project: string; app: string }>
}

export default async function AppLayout({ children, params }: AppLayoutProps) {
  const session = await requireConsoleSession()
  const { project, app } = await params

  const projects = await fetchBackend<ProjectRecord[]>("/projects", {
    token: session.token,
  }).catch(() => [] as ProjectRecord[])

  const record = projects.find((p) => p.id === app)
  if (!record) {
    notFound()
  }

  return (
    <div className="space-y-6">
      {/* Desktop: the main sidebar slides to this app's menu (see ConsoleNav).
          Mobile (no sidebar): a horizontal app bar carries the same menu. */}
      <div className="lg:hidden">
        <ProjectSubNav
          projectSlug={project}
          appId={app}
          projectName={record.project_name || record.name}
          appName={record.name}
        />
      </div>
      <main className="min-w-0">{children}</main>
    </div>
  )
}
