import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: () => {} }) }))

import { AppMarketplace } from "@/components/apps/app-marketplace"
import type { AppTemplate } from "@/lib/types"

const templates: AppTemplate[] = [
  { slug: "wordpress-with-mysql", name: "WordPress", description: "Blog", category: "cms", tags: ["blog"], logo: "svgs/wordpress.svg", port: "80" },
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

  it("marks already-installed apps", () => {
    render(<AppMarketplace templates={templates} installedProjects={["ghost"]} />)
    expect(screen.getByText("Installed")).toBeInTheDocument()
  })
})
