import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

let pathname = "/projects/shop/production"
vi.mock("next/navigation", () => ({ usePathname: () => pathname }))

const calls: string[] = []
vi.mock("@/lib/client-api", () => ({
  apiFetch: async (path: string) => {
    calls.push(path)
    if (path.endsWith("/projects")) {
      return [
        { id: "p1", slug: "shop", name: "Shop", environments: 2, apps: 2 },
        { id: "p2", slug: "blog", name: "Blog", environments: 1, apps: 0 },
      ]
    }
    if (path.endsWith("/apps")) {
      const env = { id: "e1", slug: "production", name: "Production", kind: "production" }
      return [
        { id: "s1", name: "web", kind: "app", external_id: "shop-web", database_id: null, project: { slug: "shop" }, environment: env },
        { id: "s2", name: "shop-db", kind: "database", external_id: "tdb-x", database_id: "db-1", project: { slug: "shop" }, environment: env },
      ]
    }
    if (path.includes("/projects/shop/environments")) {
      return [
        { id: "e1", slug: "production", name: "Production", kind: "production", apps: 2 },
        { id: "e2", slug: "staging", name: "Staging", kind: "staging", apps: 0 },
      ]
    }
    return []
  },
}))

import { currentPlacement, ProjectTree } from "@/components/shell/project-tree"
import { setNavOpen, useNavOpen } from "@/lib/nav-state"

// An in-memory localStorage (the test DOM doesn't provide one).
const store = new Map<string, string>()
Object.defineProperty(window, "localStorage", {
  configurable: true,
  value: {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, String(v)),
    removeItem: (k: string) => void store.delete(k),
    clear: () => store.clear(),
  },
})

beforeEach(() => {
  window.localStorage.clear()
  calls.length = 0
  pathname = "/projects/shop/production"
})
afterEach(() => cleanup())

describe("currentPlacement", () => {
  it("reads the project and environment from the path, else from the page's labels", () => {
    expect(currentPlacement("/projects/shop/staging", {})).toEqual({ project: "shop", environment: "staging" })
    expect(currentPlacement("/apps/x/env", { projectSlug: "shop", environmentSlug: "production" })).toEqual({
      project: "shop",
      environment: "production",
    })
  })
})

describe("ProjectTree", () => {
  it("opens along the current path and lists the environment's services", async () => {
    render(<ProjectTree team="acme" />)
    expect(await screen.findByRole("link", { name: /web/ })).toHaveAttribute("href", "/apps/shop-web/deployments")
    expect(screen.getByRole("link", { name: /shop-db/ })).toHaveAttribute("href", "/databases/db-1")
    // The current project is open (its environments were fetched); Blog stays closed.
    expect(calls).toContain("/api/proxy/teams/acme/projects/shop/environments")
    expect(calls.some((c) => c.includes("/projects/blog/environments"))).toBe(false)
    expect(screen.getByRole("button", { name: "Expand Blog" })).toHaveAttribute("aria-expanded", "false")
  })

  it("expands a closed project on click and remembers it", async () => {
    render(<ProjectTree team="acme" />)
    fireEvent.click(await screen.findByRole("button", { name: "Expand Blog" }))
    await waitFor(() => expect(calls.some((c) => c.includes("/projects/blog/environments"))).toBe(true))
    expect(JSON.parse(window.localStorage.getItem("tetra.nav.open") ?? "{}")).toMatchObject({ "project:p2": true })
  })
})

describe("useNavOpen", () => {
  function Probe() {
    const [open, toggle] = useNavOpen("section:Operate", true)
    return <button onClick={toggle}>{open ? "open" : "closed"}</button>
  }

  it("defaults, toggles and follows changes made elsewhere", () => {
    render(<Probe />)
    fireEvent.click(screen.getByRole("button", { name: "open" }))
    expect(screen.getByRole("button", { name: "closed" })).toBeInTheDocument()
    act(() => setNavOpen("section:Operate", true))
    expect(screen.getByRole("button", { name: "open" })).toBeInTheDocument()
  })
})
