import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { DeploymentsPanel } from "@/components/dashboard/deployments-panel"
import { KpiRail } from "@/components/dashboard/kpi-rail"
import type { RecentDeployment } from "@/lib/types"

afterEach(cleanup)

describe("KpiRail", () => {
  it("renders labels, mono values, and sub-lines", () => {
    render(
      <KpiRail
        items={[
          { label: "Projects", value: "24", sub: "2 unhealthy", tone: "warn" },
          { label: "Deploys / 24h", value: "61", sub: "98% success", tone: "ok" },
        ]}
      />,
    )
    expect(screen.getByText("Projects")).toBeInTheDocument()
    expect(screen.getByText("24")).toBeInTheDocument()
    expect(screen.getByText("2 unhealthy")).toBeInTheDocument()
    expect(screen.getByText("98% success")).toBeInTheDocument()
  })
})

describe("DeploymentsPanel", () => {
  const dep: RecentDeployment = {
    id: "d1",
    project: "storefront",
    ref: "main",
    commit: "a3f9c21",
    status: "ready",
    domain: "shop.example.com",
    created_at: new Date().toISOString(),
  }

  it("renders a deployment row with project, commit, and status label", () => {
    render(<DeploymentsPanel deployments={[dep]} />)
    expect(screen.getByText("storefront")).toBeInTheDocument()
    expect(screen.getByText("a3f9c21")).toBeInTheDocument()
    expect(screen.getByText("Ready")).toBeInTheDocument()
  })

  it("maps error status to Failed and shows an empty state", () => {
    const { rerender } = render(<DeploymentsPanel deployments={[{ ...dep, status: "error" }]} />)
    expect(screen.getByText("Failed")).toBeInTheDocument()
    rerender(<DeploymentsPanel deployments={[]} />)
    expect(screen.getByText(/no deployments yet/i)).toBeInTheDocument()
  })
})
