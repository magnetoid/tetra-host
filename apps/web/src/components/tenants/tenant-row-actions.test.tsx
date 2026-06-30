import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, render, screen } from "@testing-library/react"

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: () => {} }) }))

import { TenantRowActions } from "@/components/tenants/tenant-row-actions"
import type { TenantRecord } from "@/lib/types"

afterEach(() => cleanup())

const base: TenantRecord = {
  id: "t-1",
  name: "Acme Corp",
  slug: "acme",
  is_active: false,
  status: "pending",
  plan_key: "starter",
}

describe("TenantRowActions", () => {
  it("shows Approve and Reject buttons for pending tenants", () => {
    render(<TenantRowActions tenant={base} />)
    expect(screen.getByRole("button", { name: /Approve Acme Corp/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /Reject Acme Corp/i })).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /Suspend/i })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /Reactivate/i })).not.toBeInTheDocument()
  })

  it("shows Suspend button for active tenants", () => {
    render(<TenantRowActions tenant={{ ...base, status: "active", is_active: true }} />)
    expect(screen.getByRole("button", { name: /Suspend Acme Corp/i })).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /Approve/i })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /Reject/i })).not.toBeInTheDocument()
  })

  it("shows Reactivate button for suspended tenants", () => {
    render(<TenantRowActions tenant={{ ...base, status: "suspended" }} />)
    expect(screen.getByRole("button", { name: /Reactivate Acme Corp/i })).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /Approve/i })).not.toBeInTheDocument()
  })

  it("shows Reactivate button for rejected tenants", () => {
    render(<TenantRowActions tenant={{ ...base, status: "rejected" }} />)
    expect(screen.getByRole("button", { name: /Reactivate Acme Corp/i })).toBeInTheDocument()
  })
})
