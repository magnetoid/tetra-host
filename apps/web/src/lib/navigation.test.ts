import { describe, expect, it } from "vitest"

import { activeItem, breadcrumbsFor, resolveScope, sidebarFor } from "./navigation"

describe("resolveScope", () => {
  it("maps super-admin paths to platform scope for platform admins only", () => {
    expect(resolveScope("/tenants/5", true)).toEqual({ kind: "platform" })
    expect(resolveScope("/super-admin", true)).toEqual({ kind: "platform" })
    expect(resolveScope("/tenants/5", false)).toEqual({ kind: "team" })
  })

  it("maps project and app paths", () => {
    expect(resolveScope("/projects/web", true)).toEqual({ kind: "project", project: "web" })
    expect(resolveScope("/projects/web/apps/a1/logs", false)).toEqual({
      kind: "app",
      project: "web",
      app: "a1",
    })
  })

  it("does not confuse prefixes", () => {
    expect(resolveScope("/administrators", true)).toEqual({ kind: "team" })
    expect(resolveScope("/dashboard", true)).toEqual({ kind: "team" })
  })
})

describe("sidebarFor", () => {
  it("offers a back link to the platform only to platform admins", () => {
    expect(sidebarFor({ kind: "team" }, true).back?.href).toBe("/super-admin")
    expect(sidebarFor({ kind: "team" }, false).back).toBeUndefined()
    expect(sidebarFor({ kind: "platform" }, true).back).toBeUndefined()
  })

  it("app scope backs out to its project with the project label", () => {
    const model = sidebarFor({ kind: "app", project: "web", app: "a1" }, false, { project: "Website" })
    expect(model.back).toEqual({ href: "/projects/web", label: "Website" })
    expect(activeItem(model, "/projects/web/apps/a1/logs")?.label).toBe("Logs")
    expect(activeItem(model, "/projects/web/apps/a1")?.label).toBe("Overview")
  })
})

describe("breadcrumbsFor", () => {
  it("builds platform / team / project / app / page with no href on the last crumb", () => {
    const scope = resolveScope("/projects/web/apps/a1/env", true)
    const crumbs = breadcrumbsFor(scope, "/projects/web/apps/a1/env", true, {
      team: "Cloud Industry",
      project: "Website",
      app: "mtio",
    })
    expect(crumbs.map((c) => c.label)).toEqual(["Platform", "Cloud Industry", "Website", "mtio", "Variables"])
    expect(crumbs.at(-1)?.href).toBeUndefined()
    expect(crumbs[2].href).toBe("/projects/web")
  })

  it("omits the page crumb at a scope root and the platform crumb for team users", () => {
    const crumbs = breadcrumbsFor({ kind: "team" }, "/dashboard", false, { team: "Acme" })
    expect(crumbs).toEqual([{ label: "Acme" }])
  })
})
