import { AppShell } from "@/components/shell/app-shell"
import { requireConsoleSession } from "@/lib/auth"
import { fetchDegraded } from "@/lib/fetch-degraded"
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
  // degraded label intentionally unused — pages surface their own banners
  const projectsRes = await fetchDegraded<ProjectRecord[]>("/projects", "Projects", [], {
    token: session.token,
  })
  const projects = projectsRes.data

  return (
    <AppShell admin={session.admin} projects={groupProjects(projects)}>
      {children}
    </AppShell>
  )
}
