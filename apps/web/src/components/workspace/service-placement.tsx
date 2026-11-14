import Link from "next/link"

import { SetScopeLabels } from "@/components/shell/scope-labels"
import { fetchDegraded } from "@/lib/fetch-degraded"
import type { WorkspaceService } from "@/lib/types"
import { environmentHref, placementLabels } from "@/lib/workspace"

/**
 * Where a service lives: publishes its project/environment to the shell
 * (breadcrumbs, sidebar back link) and renders a back link to its environment.
 * Services always keep their own URL, so this is looked up, not routed.
 */
export async function ServicePlacement({
  token,
  team,
  stack,
  databaseId,
}: {
  token: string
  team: string
  stack?: string
  databaseId?: string
}) {
  const { data } = await fetchDegraded<WorkspaceService[]>(`/teams/${team}/apps`, "Services", [], { token })
  const service = data.find((s) =>
    databaseId ? s.database_id === databaseId : s.kind === "app" && s.external_id === stack,
  )
  return (
    <>
      <SetScopeLabels {...placementLabels(service)} />
      <Link href={environmentHref(service)} className="text-sm text-muted-foreground hover:text-foreground">
        ← {service ? `${service.project.name} · ${service.environment.name}` : "Projects"}
      </Link>
    </>
  )
}
