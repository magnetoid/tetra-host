import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: () => {}, push: () => {} }) }))

import { NewService } from "@/components/workspace/new-service"
import { ProjectsManager } from "@/components/workspace/projects-manager"
import { ServiceList } from "@/components/workspace/service-list"
import type { DatabaseEngine, WorkspaceProject, WorkspaceService } from "@/lib/types"
import { placementLabels, serviceHref, teamRef } from "@/lib/workspace"

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const ENGINES: DatabaseEngine[] = [
  { key: "postgres", label: "PostgreSQL", versions: ["17"], default_version: "17", supports_backup: true },
]

const REF = { id: "x", slug: "shop", name: "Shop" }
const SERVICE: WorkspaceService = {
  id: "s1", name: "blog-db", driver: "engine", kind: "database", external_id: "tdb-abc",
  database_id: "db-1", domain: "", team: { id: "t", slug: "acme", name: "Acme" }, project: REF,
  environment: { id: "e1", slug: "production", name: "Production", kind: "production" },
  updated_at: "2026-11-14T00:00:00Z",
}

describe("workspace helpers", () => {
  it("links each kind to its own page", () => {
    expect(serviceHref(SERVICE)).toBe("/databases/db-1")
    expect(serviceHref({ kind: "app", external_id: "my blog", database_id: null })).toBe(
      "/apps/my%20blog/deployments",
    )
  })

  it("derives labels and the team segment", () => {
    expect(placementLabels(SERVICE)).toMatchObject({ projectSlug: "shop", environmentSlug: "production", app: "blog-db" })
    expect(placementLabels(undefined)).toEqual({})
    expect(teamRef({ id: "a", email: "", full_name: "", is_active: true, tenant_slug: "acme" })).toBe("acme")
  })
})

describe("ProjectsManager", () => {
  it("lists projects with their counts", () => {
    const project: WorkspaceProject = {
      ...REF, team: REF, environments: 2, apps: 1, created_at: "", updated_at: "",
    }
    render(<ProjectsManager team="acme" projects={[project]} />)
    expect(screen.getByRole("link", { name: /shop/i })).toHaveAttribute("href", "/projects/shop")
    expect(screen.getByText("1 service · 2 environments")).toBeInTheDocument()
  })

  it("shows the empty state", () => {
    render(<ProjectsManager team="acme" projects={[]} />)
    expect(screen.getByText(/no projects yet/i)).toBeInTheDocument()
  })
})

describe("ServiceList", () => {
  it("shows a database with its engine and status", () => {
    render(
      <ServiceList
        services={[SERVICE]}
        runtime={{ "tdb-abc": { status: "running(1)", detail: "PostgreSQL 17 · blog-db:5432" } }}
      />,
    )
    expect(screen.getByRole("link", { name: /blog-db/ })).toHaveAttribute("href", "/databases/db-1")
    expect(screen.getByText("PostgreSQL 17 · blog-db:5432")).toBeInTheDocument()
  })
})

describe("NewService", () => {
  it("opens the picker and creates a database in the environment", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ id: "db-2" }), { status: 201 }))
    vi.stubGlobal("fetch", fetchMock)
    render(
      <NewService
        environmentId="env-1"
        environmentName="Production"
        templates={[]}
        installedProjects={[]}
        engines={ENGINES}
      />,
    )
    fireEvent.click(screen.getByRole("button", { name: /new service/i }))
    expect(screen.getByText("It will be created in Production.")).toBeInTheDocument()
    fireEvent.click(screen.getByRole("radio", { name: /database/i }))
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "shop-db" } })
    fireEvent.click(screen.getByRole("button", { name: /create database/i }))
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalled())
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe("/api/proxy/databases")
    expect(JSON.parse(String(init.body))).toMatchObject({ name: "shop-db", environment_id: "env-1" })
  })

  it("offers the git form", () => {
    render(
      <NewService environmentId="env-1" environmentName="Staging" templates={[]} installedProjects={[]} engines={ENGINES} initialOpen />,
    )
    fireEvent.click(screen.getByRole("radio", { name: /git repository/i }))
    expect(screen.getByLabelText("Git repository")).toBeInTheDocument()
  })
})
