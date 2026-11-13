import { describe, expect, it } from "vitest"

import { activeItem, breadcrumbsFor, resolveScope, sidebarFor } from "./navigation"

describe("resolveScope", () => {
  it("maps super-admin paths to platform scope for platform admins only", () => {
    expect(resolveScope("/tenants/5", true)).toEqual({ kind: "platform" })
    expect(resolveScope("/super-admin", true)).toEqual({ kind: "platform" })
    expect(resolveScope("/tenants/5", false)).toEqual({ kind: "team" })
  })

  it("maps engine app paths, but not the team-level apps list", () => {
    expect(resolveScope("/apps/mtio/metrics", false)).toEqual({ kind: "app", app: "mtio" })
    expect(resolveScope("/apps", false)).toEqual({ kind: "team" })
    expect(resolveScope("/apps/catalog", false)).toEqual({ kind: "team" })
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

  it("app scope backs out to the apps list", () => {
    const model = sidebarFor({ kind: "app", app: "mtio" }, false)
    expect(model.back).toEqual({ href: "/apps", label: "Apps" })
    expect(activeItem(model, "/apps/mtio/errors")?.label).toBe("Errors")
    expect(activeItem(model, "/apps/mtio/compute")?.label).toBe("Compute")
  })

  it("has no Coolify-era destinations in the team menu", () => {
    const hrefs = sidebarFor({ kind: "team" }, false).sections.flatMap((s) => s.items.map((i) => i.href))
    expect(hrefs).toContain("/deploys")
    expect(hrefs).not.toContain("/projects")
    // Databases are back as engine-managed databases (not Coolify's).
    expect(hrefs).toContain("/databases")
  })
})

describe("breadcrumbsFor", () => {
  it("builds platform / team / app / page with no href on the last crumb", () => {
    const scope = resolveScope("/apps/mtio/env", true)
    const crumbs = breadcrumbsFor(scope, "/apps/mtio/env", true, { team: "Cloud Industry" })
    expect(crumbs.map((c) => c.label)).toEqual(["Platform", "Cloud Industry", "mtio", "Variables"])
    expect(crumbs.at(-1)?.href).toBeUndefined()
    expect(crumbs[2].href).toBe("/apps/mtio/compute")
  })

  it("omits the page crumb at a scope root and the platform crumb for team users", () => {
    const crumbs = breadcrumbsFor({ kind: "team" }, "/dashboard", false, { team: "Acme" })
    expect(crumbs).toEqual([{ label: "Acme" }])
  })
})
