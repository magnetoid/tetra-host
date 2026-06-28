import { afterEach, describe, expect, it } from "vitest"
import { cleanup, render, screen } from "@testing-library/react"

import { AreaChart } from "@/components/charts/area-chart"

afterEach(() => cleanup())

const SERIES = [{ key: "requests", label: "Requests", color: "#7c3aed" }]

describe("AreaChart", () => {
  it("renders a placeholder when there is no data", () => {
    render(<AreaChart data={[]} series={SERIES} />)
    expect(screen.getByText("No traffic data for this window.")).toBeInTheDocument()
  })

  it("renders a chart container when given data", () => {
    const { container } = render(
      <AreaChart
        data={[
          { date: "2026-06-27", requests: 100 },
          { date: "2026-06-28", requests: 220 },
        ]}
        series={SERIES}
      />,
    )
    // Recharts renders into a responsive container; the empty-state copy must be gone.
    expect(screen.queryByText("No traffic data for this window.")).not.toBeInTheDocument()
    expect(container.querySelector(".recharts-responsive-container")).not.toBeNull()
  })
})
