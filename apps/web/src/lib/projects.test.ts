import { describe, expect, it } from "vitest"

import { activeGroup, groupProjects } from "@/lib/projects"
import type { ProjectRecord } from "@/lib/types"

function rec(over: Partial<ProjectRecord>): ProjectRecord {
  return {
    id: "x",
    name: "X",
    status: "running",
    primary_domain: "",
    repository: "",
    environment: "production",
    updated_at: "",
    healthcheck_enabled: false,
    ...over,
  }
}

describe("groupProjects", () => {
  it("collapses apps sharing a Coolify project into one entry", () => {
    const groups = groupProjects([
      rec({ id: "a1", name: "Alethia", project_uuid: "p1", project_name: "Alethia" }),
      rec({ id: "a2", name: "Alethia NEW", project_uuid: "p1", project_name: "Alethia" }),
      rec({ id: "a3", name: "crawl4ai", project_uuid: "p1", project_name: "Alethia" }),
      rec({ id: "m1", name: "Morpheus", project_uuid: "p2", project_name: "Morpheus" }),
    ])
    expect(groups).toHaveLength(2)
    const alethia = groups.find((g) => g.name === "Alethia")!
    expect(alethia.memberIds).toEqual(["a1", "a2", "a3"])
    expect(alethia.id).toBe("a1") // representative = first app
  })

  it("falls back to normalized name when unlinked to a project", () => {
    const groups = groupProjects([
      rec({ id: "s1", name: "Solo App" }),
      rec({ id: "s2", name: "solo app" }), // same normalized name
    ])
    expect(groups).toHaveLength(1)
    expect(groups[0].memberIds).toEqual(["s1", "s2"])
  })

  it("activeGroup matches any member app id", () => {
    const groups = groupProjects([
      rec({ id: "a1", project_uuid: "p1", project_name: "Alethia" }),
      rec({ id: "a2", project_uuid: "p1", project_name: "Alethia" }),
    ])
    expect(activeGroup(groups, "a2")?.name).toBe("Alethia")
    expect(activeGroup(groups, "nope")).toBeUndefined()
    expect(activeGroup(groups, undefined)).toBeUndefined()
  })
})
