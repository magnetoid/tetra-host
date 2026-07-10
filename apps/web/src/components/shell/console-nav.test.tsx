import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

vi.mock("next/navigation", () => ({ usePathname: vi.fn() }))
vi.mock("@fortawesome/react-fontawesome", () => ({ FontAwesomeIcon: () => null }))

import { usePathname } from "next/navigation"
import { ConsoleNav } from "@/components/shell/console-nav"

const projects = [{ id: "proj-1", name: "Cool App", memberIds: ["proj-1"] }]

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe("ConsoleNav context switch", () => {
  it("shows the global menu and no project header outside a project", () => {
    vi.mocked(usePathname).mockReturnValue("/dashboard")
    render(<ConsoleNav adminRole="platform_admin" projects={projects} />)
    expect(screen.getByRole("link", { name: /mail/i })).toHaveAttribute("href", "/mail")
    // strictly the global menu — no project header is rendered outside a project
    expect(screen.queryByRole("heading", { level: 2 })).toBeNull()
    expect(screen.queryByText("Cool App")).toBeNull()
  })

  it("treats the /projects list as global (no swap)", () => {
    vi.mocked(usePathname).mockReturnValue("/projects")
    render(<ConsoleNav adminRole="owner" projects={projects} />)
    expect(screen.queryByText("Cool App")).toBeNull()
  })

  it("shows ONLY the project menu inside a project (no global spillover)", () => {
    vi.mocked(usePathname).mockReturnValue("/projects/proj-1/logs")
    render(<ConsoleNav adminRole="platform_admin" projects={projects} />)
    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent("Cool App")
    const logs = screen.getByRole("link", { name: /logs/i })
    expect(logs).toHaveAttribute("href", "/projects/proj-1/logs")
    expect(logs).toHaveClass("bg-accent")
    // strict isolation — global items must NOT be present inside a project
    expect(screen.queryByRole("link", { name: /mail/i })).toBeNull()
    expect(screen.queryByRole("link", { name: /^dns$/i })).toBeNull()
    expect(screen.getByRole("link", { name: /all projects/i })).toHaveAttribute("href", "/projects")
  })

  it("falls back to 'Project' when the id is not in the known list", () => {
    vi.mocked(usePathname).mockReturnValue("/projects/ghost/env")
    render(<ConsoleNav adminRole="owner" projects={projects} />)
    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent("Project")
    expect(screen.getByRole("link", { name: /env/i })).toHaveAttribute(
      "href",
      "/projects/ghost/env",
    )
  })

  it("hides platform-admin-only items from non-platform admins", () => {
    vi.mocked(usePathname).mockReturnValue("/dashboard")
    render(<ConsoleNav adminRole="owner" projects={projects} />)
    expect(screen.queryByRole("link", { name: /tenants/i })).toBeNull()
  })
})
