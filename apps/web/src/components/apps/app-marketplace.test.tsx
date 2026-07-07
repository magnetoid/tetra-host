import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react"

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: () => {} }) }))

import { AppMarketplace } from "@/components/apps/app-marketplace"
import type { AppTemplate } from "@/lib/types"

const templates: AppTemplate[] = [
  { slug: "wordpress-with-mysql", name: "WordPress", description: "Blog engine", category: "cms", tags: ["blog", "php"], logo: "svgs/wordpress.svg", port: "80" },
  { slug: "ghost", name: "Ghost", description: "Publishing", category: "cms", tags: ["blog"], logo: "", port: "2368" },
  { slug: "redis", name: "Redis", description: "Cache", category: "database", tags: ["cache"], logo: "", port: "6379" },
]

afterEach(() => cleanup())

describe("AppMarketplace", () => {
  it("renders cards and filters by search", () => {
    render(<AppMarketplace templates={templates} installedProjects={[]} />)
    expect(screen.getByText("WordPress")).toBeInTheDocument()
    expect(screen.getByText("Redis")).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText("Search apps"), { target: { value: "redis" } })
    expect(screen.queryByText("WordPress")).not.toBeInTheDocument()
    expect(screen.getByText("Redis")).toBeInTheDocument()
  })

  it("marks already-installed apps on the card", () => {
    render(<AppMarketplace templates={templates} installedProjects={["ghost"]} />)
    expect(screen.getByText("Installed — view details")).toBeInTheDocument()
  })

  it("opens a details modal with description, tags and an Install action on card click", () => {
    render(<AppMarketplace templates={templates} installedProjects={[]} />)
    fireEvent.click(screen.getByRole("button", { name: "View details for WordPress" }))

    const dialog = screen.getByRole("dialog")
    expect(within(dialog).getByText("Blog engine")).toBeInTheDocument()
    expect(within(dialog).getByText("php")).toBeInTheDocument()
    expect(within(dialog).getByText("wordpress-with-mysql")).toBeInTheDocument()
    expect(within(dialog).getByRole("button", { name: /^Install$/ })).toBeEnabled()
  })

  it("shows the Install action as disabled/Installed for an installed app", () => {
    render(<AppMarketplace templates={templates} installedProjects={["ghost"]} />)
    fireEvent.click(screen.getByRole("button", { name: "View details for Ghost" }))
    const dialog = screen.getByRole("dialog")
    expect(within(dialog).getByRole("button", { name: /Installed/ })).toBeDisabled()
  })
})
