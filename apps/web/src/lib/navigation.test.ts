import { describe, expect, it } from "vitest"

import { activeItem, breadcrumbsFor, resolveScope, sidebarFor, teamSections } from "./navigation"

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

  it("a service backs out to its environment, or to Projects when unknown", () => {
    const model = sidebarFor({ kind: "app", app: "mtio" }, false)
    expect(model.back).toEqual({ href: "/projects", label: "Projects" })
    expect(activeItem(model, "/apps/mtio/errors")?.label).toBe("Errors")
    expect(activeItem(model, "/apps/mtio/deployments")?.label).toBe("Deployments")
    const placed = sidebarFor({ kind: "database", id: "db-1" }, false, {
      project: "Shop", projectSlug: "shop", environmentSlug: "production",
    })
    expect(placed.back).toEqual({ href: "/projects/shop/production", label: "Shop" })
    expect(activeItem(placed, "/databases/db-1")?.label).toBe("Overview")
  })

  it("the team menu is projects-first; services live inside projects", () => {
    const hrefs = sidebarFor({ kind: "team" }, false).sections.flatMap((s) => s.items.map((i) => i.href))
    expect(hrefs.slice(0, 2)).toEqual(["/dashboard", "/projects"])
    expect(hrefs).toContain("/deploys")
    expect(hrefs).not.toContain("/apps")
    expect(hrefs).not.toContain("/databases")
  })

  it("project pages keep the team menu with Projects active", () => {
    const model = sidebarFor({ kind: "project", project: "shop", environment: "production" }, false)
    expect(activeItem(model, "/projects/shop/production")?.label).toBe("Projects")
  })
})

describe("breadcrumbsFor", () => {
  it("names the domain on a domain's page", () => {
    const crumbs = breadcrumbsFor(resolveScope("/domains/acme.test/dns", false), "/domains/acme.test/dns", false, { team: "Acme" })
    expect(crumbs).toEqual([
      { label: "Acme", href: "/dashboard" },
      { label: "Domains", href: "/domains" },
      { label: "acme.test" },
    ])
  })

  it("keeps DNS and Mail out of the team menu (they live in Domains)", () => {
    const labels = teamSections.flatMap((s) => s.items.map((i) => i.label))
    expect(labels).not.toContain("DNS")
    expect(labels).not.toContain("Mail")
    expect(labels).toContain("Domains")
  })

  it("builds platform / team / app / page with no href on the last crumb", () => {
    const scope = resolveScope("/apps/mtio/env", true)
    const crumbs = breadcrumbsFor(scope, "/apps/mtio/env", true, { team: "Cloud Industry" })
    expect(crumbs.map((c) => c.label)).toEqual(["Platform", "Cloud Industry", "mtio", "Variables"])
    expect(crumbs.at(-1)?.href).toBeUndefined()
    expect(crumbs[2].href).toBe("/apps/mtio/deployments")
  })

  it("puts a placed service under its project and environment", () => {
    const labels = {
      team: "Acme", app: "blog-db", project: "Shop", projectSlug: "shop",
      environment: "Production", environmentSlug: "production",
    }
    const crumbs = breadcrumbsFor(resolveScope("/databases/db-1", false), "/databases/db-1", false, labels)
    expect(crumbs).toEqual([
      { label: "Acme", href: "/dashboard" },
      { label: "Shop", href: "/projects/shop" },
      { label: "Production", href: "/projects/shop/production" },
      { label: "blog-db" },
    ])
  })

  it("project scope shows project / environment", () => {
    const scope = resolveScope("/projects/shop/staging", false)
    expect(scope).toEqual({ kind: "project", project: "shop", environment: "staging" })
    const crumbs = breadcrumbsFor(scope, "/projects/shop/staging", false, { team: "Acme", project: "Shop", environment: "Staging" })
    expect(crumbs.map((c) => c.label)).toEqual(["Acme", "Shop", "Staging"])
    expect(resolveScope("/projects", false)).toEqual({ kind: "team" })
  })

  it("omits the page crumb at a scope root and the platform crumb for team users", () => {
    const crumbs = breadcrumbsFor({ kind: "team" }, "/dashboard", false, { team: "Acme" })
    expect(crumbs).toEqual([{ label: "Acme" }])
  })
})
