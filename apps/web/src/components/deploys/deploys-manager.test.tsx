import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {}, refresh: () => {} }) }))

import { DeploysManager } from "@/components/deploys/deploys-manager"
import type { DeploymentRecord } from "@/lib/types"

afterEach(() => cleanup())

const READY: DeploymentRecord = {
  id: "dep-1", project: "blog", status: "ready", git_url: "https://github.com/x/y",
  ref: "main", builder: "nixpacks", image: "tetra-blog:abc123", commit: "abc123def",
  port: 3000, domain: "blog.apps.test", log: "", error: "", created_at: "2026-07-02T00:00:00",
}

describe("DeploysManager", () => {
  it("renders the deploy form and a ready deployment with rollback", () => {
    render(<DeploysManager deployments={[READY]} />)
    expect(screen.getByLabelText("Git repository")).toBeInTheDocument()
    expect(screen.getByLabelText("Name")).toBeInTheDocument()
    expect(screen.getByText("blog")).toBeInTheDocument()
    expect(screen.getByText("blog.apps.test")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /rollback to this/i })).toBeInTheDocument()
  })

  it("marks a marketplace app install and hides git rollback for it", () => {
    render(
      <DeploysManager
        deployments={[{ ...READY, id: "dep-app", builder: "app", git_url: "", ref: "", commit: "" }]}
      />,
    )
    expect(screen.getByText("marketplace app")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /rollback/i })).not.toBeInTheDocument()
  })

  it("hides rollback for failed deployments and shows the empty state", () => {
    render(
      <DeploysManager deployments={[{ ...READY, id: "dep-2", status: "error", image: "" }]} />,
    )
    expect(screen.queryByRole("button", { name: /rollback/i })).not.toBeInTheDocument()

    cleanup()
    render(<DeploysManager deployments={[]} />)
    expect(screen.getByText(/no deployments yet/i)).toBeInTheDocument()
  })
})
