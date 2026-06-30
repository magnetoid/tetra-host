import { afterEach, describe, expect, it } from "vitest"
import { cleanup, render, screen } from "@testing-library/react"

import { BarList } from "@/components/charts/bar-list"

afterEach(() => cleanup())

describe("BarList", () => {
  it("renders each bar with its name and formatted value", () => {
    render(
      <BarList
        data={[
          { name: "Projects", value: 5 },
          { name: "DNS zones", value: 36 },
        ]}
      />,
    )
    expect(screen.getByText("Projects")).toBeInTheDocument()
    expect(screen.getByText("5")).toBeInTheDocument()
    expect(screen.getByText("DNS zones")).toBeInTheDocument()
    expect(screen.getByText("36")).toBeInTheDocument()
  })

  it("applies a custom value formatter", () => {
    render(<BarList data={[{ name: "Traffic", value: 1024 }]} valueFormatter={(n) => `${n / 1024}k`} />)
    expect(screen.getByText("1k")).toBeInTheDocument()
  })
})
