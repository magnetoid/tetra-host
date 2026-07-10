import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: () => {} }) }))

import { TeamManager } from "@/components/team/team-manager"
import type { TeamResponse } from "@/lib/types"

afterEach(() => cleanup())

const TEAM: TeamResponse = {
  members: [
    {
      id: "owner1",
      email: "owner@acme.test",
      full_name: "Acme Owner",
      role: "owner",
      is_active: true,
    },
    {
      id: "mate1",
      email: "mate@acme.test",
      full_name: "Team Mate",
      role: "member",
      is_active: true,
    },
  ],
  invites: [
    { id: "inv1", email: "pending@acme.test", role: "admin", status: "pending" },
  ],
}

describe("TeamManager", () => {
  it("owner sees the invite form, members, and a pending invite with actions", () => {
    render(<TeamManager team={TEAM} currentRole="owner" currentAdminId="owner1" />)
    expect(screen.getByLabelText("Invite email")).toBeInTheDocument()
    expect(screen.getByText("Team Mate")).toBeInTheDocument()
    expect(screen.getByText("pending@acme.test")).toBeInTheDocument()
    // A manageable (non-self, non-owner) member exposes the promote action.
    expect(screen.getByRole("button", { name: /make admin/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /revoke/i })).toBeInTheDocument()
  })

  it("members cannot manage the team (no invite form, no member actions)", () => {
    render(<TeamManager team={TEAM} currentRole="member" currentAdminId="mate1" />)
    expect(screen.queryByLabelText("Invite email")).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /make admin/i })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /revoke/i })).not.toBeInTheDocument()
    // Roster is still visible to everyone.
    expect(screen.getByText("Acme Owner")).toBeInTheDocument()
  })
})
