import { cleanup, render, screen, within } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

// Mock next/navigation before importing the component under test
vi.mock("next/navigation", () => ({
  usePathname: vi.fn(),
}))

// Mock FontAwesome to avoid SVG rendering complexity in tests
vi.mock("@fortawesome/react-fontawesome", () => ({
  FontAwesomeIcon: () => null,
}))

import { usePathname } from "next/navigation"
import { ProjectSubNav } from "@/components/projects/project-sub-nav"

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe("ProjectSubNav", () => {
  const projectId = "proj-abc"
  const projectName = "My Awesome App"

  function setup(pathname: string) {
    vi.mocked(usePathname).mockReturnValue(pathname)
    return render(<ProjectSubNav projectId={projectId} projectName={projectName} />)
  }

  it("renders all 8 nav links (plus a back link)", () => {
    setup(`/projects/${projectId}`)
    // The 8 menu items live in the <nav>; a "← Projects" back link sits in the header.
    const nav = screen.getByRole("navigation")
    expect(within(nav).getAllByRole("link")).toHaveLength(8)
    expect(screen.getByRole("link", { name: /back to projects/i })).toHaveAttribute(
      "href",
      "/projects",
    )
  })

  it("renders the project name", () => {
    setup(`/projects/${projectId}`)
    expect(screen.getByText(projectName)).toBeInTheDocument()
  })

  it("marks Overview active on the exact root path", () => {
    setup(`/projects/${projectId}`)
    const overviewLink = screen.getByRole("link", { name: /overview/i })
    expect(overviewLink).toHaveClass("bg-accent")
  })

  it("does NOT mark Overview active on a sub-path", () => {
    setup(`/projects/${projectId}/deployments`)
    const overviewLink = screen.getByRole("link", { name: /overview/i })
    expect(overviewLink).not.toHaveClass("bg-accent")
  })

  it("marks Deployments active on its sub-path", () => {
    setup(`/projects/${projectId}/deployments`)
    const deploymentsLink = screen.getByRole("link", { name: /deployments/i })
    expect(deploymentsLink).toHaveClass("bg-accent")
  })

  it("marks Logs active on its sub-path", () => {
    setup(`/projects/${projectId}/logs`)
    const logsLink = screen.getByRole("link", { name: /logs/i })
    expect(logsLink).toHaveClass("bg-accent")
  })

  it("links point to the correct project URLs", () => {
    setup(`/projects/${projectId}`)
    const base = `/projects/${projectId}`
    expect(screen.getByRole("link", { name: /overview/i })).toHaveAttribute("href", base)
    expect(screen.getByRole("link", { name: /deployments/i })).toHaveAttribute(
      "href",
      `${base}/deployments`,
    )
    expect(screen.getByRole("link", { name: /env/i })).toHaveAttribute("href", `${base}/env`)
  })
})
