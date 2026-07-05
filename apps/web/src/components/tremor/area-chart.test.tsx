import { afterEach, describe, expect, it } from "vitest"
import { cleanup, render, screen } from "@testing-library/react"

import { AreaChart } from "@/components/tremor/area-chart"

afterEach(() => cleanup())

describe("tremor/AreaChart", () => {
  it("renders the empty message when there is no data", () => {
    render(<AreaChart data={[]} index="date" categories={["requests"]} emptyMessage="Nothing yet." />)
    expect(screen.getByText("Nothing yet.")).toBeInTheDocument()
  })

  it("renders a chart container and legend labels when given data", () => {
    const { container } = render(
      <AreaChart
        data={[
          { date: "2026-06-27", requests: 100 },
          { date: "2026-06-28", requests: 220 },
        ]}
        index="date"
        categories={["requests"]}
        categoryLabels={{ requests: "Requests" }}
      />,
    )
    expect(screen.getByText("Requests")).toBeInTheDocument()
    expect(container.querySelector(".recharts-wrapper")).not.toBeNull()
  })
})
