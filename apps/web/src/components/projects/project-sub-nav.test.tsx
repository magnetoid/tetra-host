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
  const projectSlug = "proj-abc"
  const appId = "app-xyz"
  const projectName = "My Project"
  const appName = "My Awesome App"
  const base = `/projects/${projectSlug}/apps/${appId}`

  function setup(pathname: string) {
    vi.mocked(usePathname).mockReturnValue(pathname)
    return render(
      <ProjectSubNav
        projectSlug={projectSlug}
        appId={appId}
        projectName={projectName}
        appName={appName}
      />,
    )
  }

  it("renders all 8 nav links (plus a back link)", () => {
    setup(`${base}/deployments`)
    // The 8 menu items (Overview + 7 tabs) live in the <nav>; a back link sits in the header.
    const nav = screen.getByRole("navigation")
    expect(within(nav).getAllByRole("link")).toHaveLength(8)
    expect(screen.getByRole("link", { name: new RegExp(`back to ${projectName}`, "i") })).toHaveAttribute(
      "href",
      `/projects/${projectSlug}`,
    )
  })

  it("renders the app name", () => {
    setup(`${base}/deployments`)
    expect(screen.getByText(appName)).toBeInTheDocument()
  })

  it("marks Deployments active on its sub-path", () => {
    setup(`${base}/deployments`)
    const deploymentsLink = screen.getByRole("link", { name: /deployments/i })
    expect(deploymentsLink).toHaveClass("bg-accent")
  })

  it("marks Logs active on its sub-path", () => {
    setup(`${base}/logs`)
    const logsLink = screen.getByRole("link", { name: /logs/i })
    expect(logsLink).toHaveClass("bg-accent")
  })

  it("links point to the correct app URLs", () => {
    setup(`${base}/deployments`)
    expect(screen.getByRole("link", { name: /deployments/i })).toHaveAttribute(
      "href",
      `${base}/deployments`,
    )
    expect(screen.getByRole("link", { name: /env/i })).toHaveAttribute("href", `${base}/env`)
  })
})
