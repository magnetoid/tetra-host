import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

vi.mock("next/navigation", () => ({ usePathname: vi.fn() }))
vi.mock("@fortawesome/react-fontawesome", () => ({ FontAwesomeIcon: () => null }))

import { usePathname } from "next/navigation"
import { ConsoleNav } from "@/components/shell/console-nav"

const projects = [
  {
    slug: "proj-1",
    id: "app-1",
    name: "Cool Project",
    memberIds: ["app-1"],
    apps: [{ id: "app-1", name: "Cool App" }],
  },
]

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe("ConsoleNav context switch", () => {
  it("shows the global menu and no app header outside an app", () => {
    vi.mocked(usePathname).mockReturnValue("/dashboard")
    render(<ConsoleNav adminRole="platform_admin" projects={projects} />)
    expect(screen.getByRole("link", { name: /mail/i })).toHaveAttribute("href", "/mail")
    // strictly the global menu — no app header is rendered outside an app
    expect(screen.queryByRole("heading", { level: 2 })).toBeNull()
    expect(screen.queryByText("Cool App")).toBeNull()
  })

  it("treats the /projects list as global (no swap)", () => {
    vi.mocked(usePathname).mockReturnValue("/projects")
    render(<ConsoleNav adminRole="owner" projects={projects} />)
    expect(screen.queryByText("Cool App")).toBeNull()
  })

  it("treats the project detail page as global (app menu only appears inside an app)", () => {
    vi.mocked(usePathname).mockReturnValue("/projects/proj-1")
    render(<ConsoleNav adminRole="owner" projects={projects} />)
    expect(screen.queryByRole("heading", { level: 2 })).toBeNull()
    expect(screen.getByRole("link", { name: /mail/i })).toHaveAttribute("href", "/mail")
  })

  it("shows ONLY the app menu inside an app (no global spillover)", () => {
    vi.mocked(usePathname).mockReturnValue("/projects/proj-1/apps/app-1/logs")
    render(<ConsoleNav adminRole="platform_admin" projects={projects} />)
    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent("Cool App")
    const logs = screen.getByRole("link", { name: /logs/i })
    expect(logs).toHaveAttribute("href", "/projects/proj-1/apps/app-1/logs")
    expect(logs).toHaveClass("bg-accent")
    // strict isolation — global items must NOT be present inside an app
    expect(screen.queryByRole("link", { name: /mail/i })).toBeNull()
    expect(screen.queryByRole("link", { name: /^dns$/i })).toBeNull()
    // back link returns to the owning project detail page
    expect(screen.getByRole("link", { name: /cool project/i })).toHaveAttribute(
      "href",
      "/projects/proj-1",
    )
  })

  it("falls back to 'App' when the app is not in the known list", () => {
    vi.mocked(usePathname).mockReturnValue("/projects/ghost/apps/appX/env")
    render(<ConsoleNav adminRole="owner" projects={projects} />)
    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent("App")
    expect(screen.getByRole("link", { name: /env/i })).toHaveAttribute(
      "href",
      "/projects/ghost/apps/appX/env",
    )
  })

  it("hides platform-admin-only items from non-platform admins", () => {
    vi.mocked(usePathname).mockReturnValue("/dashboard")
    render(<ConsoleNav adminRole="owner" projects={projects} />)
    expect(screen.queryByRole("link", { name: /tenants/i })).toBeNull()
  })

  it("swaps to the dedicated Super Admin menu + back link inside the admin section", () => {
    vi.mocked(usePathname).mockReturnValue("/tenants")
    render(<ConsoleNav adminRole="platform_admin" projects={projects} />)
    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent("Super Admin")
    expect(screen.getByRole("link", { name: /tenants/i })).toHaveAttribute("href", "/tenants")
    expect(screen.getByRole("link", { name: /plans/i })).toHaveAttribute("href", "/plans")
    // back link exits to the console; global items are not mounted here
    expect(screen.getByRole("link", { name: /back to console/i })).toHaveAttribute(
      "href",
      "/dashboard",
    )
    expect(screen.queryByRole("link", { name: /^mail$/i })).toBeNull()
  })

  it("does NOT swap to the admin menu for non-platform admins on the same path", () => {
    vi.mocked(usePathname).mockReturnValue("/status")
    render(<ConsoleNav adminRole="owner" projects={projects} />)
    expect(screen.queryByRole("heading", { level: 2 })).toBeNull()
    expect(screen.getByRole("link", { name: /mail/i })).toHaveAttribute("href", "/mail")
  })
})
