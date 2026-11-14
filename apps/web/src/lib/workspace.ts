import type { AdminRecord, WorkspaceService } from "@/lib/types"
import { projectHref, type ScopeLabels } from "@/lib/navigation"

/** The team the signed-in admin works in, as the `/teams/{team}` path segment. */
export function teamRef(admin: AdminRecord): string {
  return encodeURIComponent(admin.tenant_slug || admin.tenant_id || "")
}

/** A service's console address: an app's deployments, or the database page. */
export function serviceHref(service: Pick<WorkspaceService, "kind" | "external_id" | "database_id">): string {
  if (service.kind === "database" && service.database_id) {
    return `/databases/${encodeURIComponent(service.database_id)}`
  }
  return `/apps/${encodeURIComponent(service.external_id)}/deployments`
}

/** The labels a service page publishes so the shell can show where it lives. */
export function placementLabels(service: WorkspaceService | undefined): Omit<ScopeLabels, "team"> {
  if (!service) return {}
  return {
    app: service.name,
    project: service.project.name,
    projectSlug: service.project.slug,
    environment: service.environment.name,
    environmentSlug: service.environment.slug,
  }
}

/** The environment page a service belongs to, or the project list. */
export function environmentHref(service: WorkspaceService | undefined): string {
  return service ? projectHref(service.project.slug, service.environment.slug) : "/projects"
}
