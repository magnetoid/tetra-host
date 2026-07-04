import { cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it } from "vitest"

import { UserMenu } from "@/components/ui/user-menu"
import type { AdminRecord } from "@/lib/types"

afterEach(cleanup)

const OWNER: AdminRecord = {
  id: "a1",
  email: "owner@acme.test",
  full_name: "Ada Owner",
  is_active: true,
  role: "owner",
  tenant_name: "Acme",
}

const PLATFORM_ADMIN: AdminRecord = { ...OWNER, email: "root@ci.test", role: "platform_admin" }

describe("UserMenu", () => {
  it("is closed until the trigger is clicked", () => {
    render(<UserMenu admin={OWNER} />)
    expect(screen.queryByRole("menu")).not.toBeInTheDocument()
  })

  it("opens on click and shows Account + Logout", async () => {
    const user = userEvent.setup()
    render(<UserMenu admin={OWNER} />)
    await user.click(screen.getByRole("button", { name: /ada owner/i }))
    expect(screen.getByRole("menu")).toBeInTheDocument()
    expect(screen.getByRole("menuitem", { name: /account/i })).toHaveAttribute("href", "/account")
    expect(screen.getByRole("menuitem", { name: /log out/i })).toBeInTheDocument()
  })

  it("hides Super Admin for owners", async () => {
    const user = userEvent.setup()
    render(<UserMenu admin={OWNER} />)
    await user.click(screen.getByRole("button", { name: /ada owner/i }))
    expect(screen.queryByRole("menuitem", { name: /super admin/i })).not.toBeInTheDocument()
  })

  it("shows Super Admin → /super-admin for platform admins", async () => {
    const user = userEvent.setup()
    render(<UserMenu admin={PLATFORM_ADMIN} />)
    await user.click(screen.getByRole("button", { name: /ada owner/i }))
    expect(screen.getByRole("menuitem", { name: /super admin/i })).toHaveAttribute(
      "href",
      "/super-admin",
    )
  })

  it("toggles the theme attribute + cookie on the theme item", async () => {
    document.documentElement.dataset.theme = "dark"
    const user = userEvent.setup()
    render(<UserMenu admin={OWNER} />)
    await user.click(screen.getByRole("button", { name: /ada owner/i }))
    await user.click(screen.getByRole("menuitem", { name: /light mode/i }))
    expect(document.documentElement.dataset.theme).toBe("light")
    expect(document.cookie).toContain("tetra-theme=light")
  })

  it("closes on Escape", async () => {
    const user = userEvent.setup()
    render(<UserMenu admin={OWNER} />)
    await user.click(screen.getByRole("button", { name: /ada owner/i }))
    expect(screen.getByRole("menu")).toBeInTheDocument()
    await user.keyboard("{Escape}")
    expect(screen.queryByRole("menu")).not.toBeInTheDocument()
  })
})
