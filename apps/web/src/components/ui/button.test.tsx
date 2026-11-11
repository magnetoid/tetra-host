import { afterEach, describe, expect, it } from "vitest"
import { cleanup, render, screen } from "@testing-library/react"
import { faPlus } from "@fortawesome/free-solid-svg-icons"

import { Button } from "@/components/ui/button"

afterEach(() => cleanup())

describe("Button", () => {
  it("renders a button with its icon", () => {
    render(<Button icon={faPlus}>Add</Button>)
    const button = screen.getByRole("button", { name: "Add" })
    expect(button.querySelector("svg")).not.toBeNull()
  })

  it("renders as its single child when asChild is set", () => {
    render(
      <Button variant="primary" asChild>
        <a href="/dashboard">Go to overview</a>
      </Button>,
    )
    const link = screen.getByRole("link", { name: "Go to overview" })
    expect(link.getAttribute("href")).toBe("/dashboard")
    expect(link.className).toContain("bg-primary")
    expect(screen.queryByRole("button")).toBeNull()
  })
})
