import { afterEach, describe, expect, it } from "vitest"
import { cleanup, render, screen } from "@testing-library/react"

import { DonutChart, DonutLegend } from "@/components/tremor/donut-chart"

afterEach(() => cleanup())

const DATA = [
  { name: "Connected", value: 3 },
  { name: "Degraded", value: 1 },
]

describe("tremor/DonutChart", () => {
  it("renders the centered value and label", () => {
    render(<DonutChart data={DATA} centerValue="3/4" centerLabel="healthy" />)
    expect(screen.getByText("3/4")).toBeInTheDocument()
    expect(screen.getByText("healthy")).toBeInTheDocument()
  })
})

describe("tremor/DonutLegend", () => {
  it("renders each slice name with its formatted value", () => {
    render(<DonutLegend data={DATA} valueFormatter={(n) => `${n} providers`} />)
    expect(screen.getByText("Connected")).toBeInTheDocument()
    expect(screen.getByText("3 providers")).toBeInTheDocument()
    expect(screen.getByText("Degraded")).toBeInTheDocument()
  })
})
