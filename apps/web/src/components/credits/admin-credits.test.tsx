import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: () => {} }) }))

import { AdminCredits } from "@/components/credits/admin-credits"
import type { TenantCreditOverview } from "@/lib/types"

afterEach(() => cleanup())

const ROWS: TenantCreditOverview[] = [
  { tenant_id: "t-1", tenant_name: "Acme", balance_usd: 4.5, spend_30d_usd: 0.5, requests_30d: 12 },
]

describe("AdminCredits", () => {
  it("lists tenants with balance + a top-up control", () => {
    render(<AdminCredits rows={ROWS} />)
    expect(screen.getByText("Acme")).toBeInTheDocument()
    expect(screen.getByText("$4.50")).toBeInTheDocument()
    expect(screen.getByLabelText("Top up Acme")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /add/i })).toBeInTheDocument()
  })

  it("shows an empty state with no tenants", () => {
    render(<AdminCredits rows={[]} />)
    expect(screen.getByText(/no tenants yet/i)).toBeInTheDocument()
  })
})
