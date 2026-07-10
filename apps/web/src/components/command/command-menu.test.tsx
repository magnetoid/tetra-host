import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {} }) }))

import { CommandMenu } from "@/components/command/command-menu"

afterEach(() => cleanup())

describe("CommandMenu", () => {
  it("opens on the trigger and lists navigation + actions", async () => {
    render(<CommandMenu adminRole="platform_admin" />)
    fireEvent.click(screen.getByRole("button", { name: /search/i }))
    expect(await screen.findByText("Deployments")).toBeInTheDocument()
    expect(screen.getByText("Toggle theme")).toBeInTheDocument()
  })

  it("hides platform-admin-only destinations from non-platform admins", async () => {
    render(<CommandMenu adminRole="owner" />)
    fireEvent.click(screen.getByRole("button", { name: /search/i }))
    expect(await screen.findByText("Deployments")).toBeInTheDocument()
    expect(screen.queryByText("Tenants")).not.toBeInTheDocument()
  })
})
