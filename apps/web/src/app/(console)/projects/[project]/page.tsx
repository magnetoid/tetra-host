import { notFound, redirect } from "next/navigation"

import { ApiError, fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import { projectHref } from "@/lib/navigation"
import type { WorkspaceEnvironment } from "@/lib/types"
import { teamRef } from "@/lib/workspace"

/** A project opens on its production environment (or its first one). */
export default async function ProjectPage({ params }: { params: Promise<{ project: string }> }) {
  const session = await requireConsoleSession()
  const { project } = await params
  let environments: WorkspaceEnvironment[]
  try {
    environments = await fetchBackend<WorkspaceEnvironment[]>(
      `/teams/${teamRef(session.admin)}/projects/${encodeURIComponent(project)}/environments`,
      { token: session.token },
    )
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) notFound()
    throw err
  }
  const target = environments.find((e) => e.kind === "production") ?? environments[0]
  if (!target) notFound()
  redirect(projectHref(project, target.slug))
}
