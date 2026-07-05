import { afterEach, describe, expect, it } from "vitest"
import { cleanup, render, screen } from "@testing-library/react"

import { Badge } from "@/components/ui/badge"

afterEach(() => cleanup())

describe("Badge", () => {
  it("renders its children", () => {
    render(<Badge>Running</Badge>)
    expect(screen.getByText("Running")).toBeInTheDocument()
  })

  it("applies the success variant classes", () => {
    render(<Badge variant="success">Active</Badge>)
    const el = screen.getByText("Active")
    expect(el.className).toContain("text-status-ok")
  })

  it("applies the destructive variant classes", () => {
    render(<Badge variant="destructive">Error</Badge>)
    const el = screen.getByText("Error")
    expect(el.className).toContain("bg-destructive")
  })

  it("merges custom className", () => {
    render(<Badge className="my-custom">Label</Badge>)
    const el = screen.getByText("Label")
    expect(el.className).toContain("my-custom")
  })
})
