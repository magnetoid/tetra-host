import type { ProjectRecord } from "@/lib/types"

/**
 * A project as the switchers/nav see it — one entry per Coolify project (or
 * standalone app), carrying every member application id so the active project
 * still resolves when the route is inside any of its apps.
 */
export type ProjectGroup = {
  id: string // representative app id (nav target)
  name: string
  memberIds: string[]
}

const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, "")

/**
 * Collapse the flat application list into project groups (tenant > project >
 * deployment), mirroring the projects page. Apps sharing a Coolify project —
 * or a normalized name when unlinked — become one entry.
 */
export function groupProjects(records: ProjectRecord[]): ProjectGroup[] {
  const groups = new Map<string, ProjectGroup>()
  for (const p of records) {
    const key = p.project_uuid || `name:${norm(p.project_name || p.name)}`
    const group = groups.get(key) ?? {
      id: p.id,
      name: p.project_name || p.name,
      memberIds: [],
    }
    group.memberIds.push(p.id)
    groups.set(key, group)
  }
  return [...groups.values()].sort((a, b) => a.name.localeCompare(b.name))
}

/** Find the group that owns a given app/route id. */
export function activeGroup(groups: ProjectGroup[], activeId: string | undefined) {
  if (!activeId) return undefined
  return groups.find((g) => g.memberIds.includes(activeId) || g.id === activeId)
}
