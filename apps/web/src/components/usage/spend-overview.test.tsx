import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { SpendOverview } from "@/components/usage/spend-overview"
import type { AiUsageReport, CreditBalance } from "@/lib/types"

afterEach(() => cleanup())

const CREDIT: CreditBalance = {
  balance_usd: 4.9974,
  transactions: [
    { kind: "topup", amount_usd: 5, reference: "admin top-up", created_at: "2026-07-10T00:00:00" },
    { kind: "debit", amount_usd: -0.0026, reference: "gen-abc", created_at: "2026-07-10T01:00:00" },
  ],
}

const AI: AiUsageReport = {
  total_billed_usd: 0.0026,
  total_cost_usd: 0.002,
  total_requests: 1,
  by_model: [{ model: "openai/gpt-4o-mini", requests: 1, billed_usd: 0.0026 }],
  events: [],
}

describe("SpendOverview", () => {
  it("shows balance, spend, requests, and the per-model breakdown", () => {
    render(<SpendOverview credit={CREDIT} ai={AI} />)
    expect(screen.getByText("AI credit balance")).toBeInTheDocument()
    expect(screen.getByText("AI spend")).toBeInTheDocument()
    expect(screen.getByText(/openai\/gpt-4o-mini/)).toBeInTheDocument()
    expect(screen.getByText("admin top-up")).toBeInTheDocument()
  })

  it("nudges a top-up when the balance is empty", () => {
    render(
      <SpendOverview
        credit={{ balance_usd: 0, transactions: [] }}
        ai={{ total_billed_usd: 0, total_cost_usd: 0, total_requests: 0, by_model: [], events: [] }}
      />,
    )
    expect(screen.getByText(/top up to use the AI gateway/i)).toBeInTheDocument()
    expect(screen.getByText(/no AI usage yet/i)).toBeInTheDocument()
  })
})
