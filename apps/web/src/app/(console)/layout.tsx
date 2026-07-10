import { AppShell } from "@/components/shell/app-shell"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import { groupProjects } from "@/lib/projects"
import type { ProjectRecord } from "@/lib/types"

export default async function ConsoleLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  const session = await requireConsoleSession()

  // Powers the sidebar's project-context switch (resolves the project name when
  // the route is inside a project). The per-project layout fetches the same list
  // for validation; identical GETs are request-memoized within a render.
  const projects = await fetchBackend<ProjectRecord[]>("/projects", {
    token: session.token,
  }).catch(() => [] as ProjectRecord[])

  return (
    <AppShell admin={session.admin} projects={groupProjects(projects)}>
      {children}
    </AppShell>
  )
}
