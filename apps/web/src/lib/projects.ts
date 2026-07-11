import type { ProjectRecord } from "@/lib/types"

/** One app inside a project group (the "deployment" tier's owning resource). */
export type ProjectApp = { id: string; name: string }

/**
 * A project as the switchers/nav see it — one entry per Coolify project (or
 * standalone app). Identified in the URL by {@link ProjectGroup.slug}; carries
 * every member app so the active project + app still resolve when the route is
 * inside `/projects/<slug>/apps/<appId>`.
 */
export type ProjectGroup = {
  slug: string // stable URL segment (project_uuid or name key)
  id: string // representative app id (first app)
  name: string
  memberIds: string[]
  apps: ProjectApp[]
}

const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, "")

/**
 * The stable URL slug for the project that owns an app record — the Coolify
 * project uuid when linked, else a normalized name key. Shared by the projects
 * list, the project detail page, and the switchers so links + matching agree.
 */
export function projectSlug(record: Pick<ProjectRecord, "project_uuid" | "project_name" | "name">) {
  return record.project_uuid || `name:${norm(record.project_name || record.name)}`
}

/**
 * Collapse the flat application list into project groups (tenant > project >
 * app > deployment), mirroring the projects page. Apps sharing a Coolify
 * project — or a normalized name when unlinked — become one entry.
 */
export function groupProjects(records: ProjectRecord[]): ProjectGroup[] {
  const groups = new Map<string, ProjectGroup>()
  for (const p of records) {
    const slug = projectSlug(p)
    const group =
      groups.get(slug) ??
      ({
        slug,
        id: p.id,
        name: p.project_name || p.name,
        memberIds: [],
        apps: [],
      } as ProjectGroup)
    group.memberIds.push(p.id)
    group.apps.push({ id: p.id, name: p.name })
    groups.set(slug, group)
  }
  return [...groups.values()].sort((a, b) => a.name.localeCompare(b.name))
}

/** Find the group for a given URL slug (or, as a fallback, an owned app id). */
export function activeGroup(groups: ProjectGroup[], active: string | undefined) {
  if (!active) return undefined
  const slug = decodeURIComponent(active)
  return groups.find((g) => g.slug === slug || g.memberIds.includes(active) || g.id === active)
}
