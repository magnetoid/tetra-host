import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, render, screen } from "@testing-library/react"

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: () => {} }) }))

import { PlanForm } from "@/components/plans/plan-form"
import type { Plan } from "@/lib/types"

const samplePlan: Plan = {
  id: "plan-1",
  key: "starter",
  name: "Starter Plan",
  description: "Entry-level plan",
  price_cents: 999,
  currency: "usd",
  max_apps: 3,
  max_domains: 5,
  cpu_millicores: 500,
  mem_mb: 512,
  disk_mb: 5120,
  is_archived: false,
  sort_order: 1,
}

afterEach(() => cleanup())

describe("PlanForm (create mode)", () => {
  it("renders key, name, and create button", () => {
    render(<PlanForm />)
    expect(screen.getByLabelText("Plan key")).toBeInTheDocument()
    expect(screen.getByLabelText("Plan name")).toBeInTheDocument()
    expect(screen.getByLabelText("Price cents")).toBeInTheDocument()
    expect(screen.getByLabelText("Max apps")).toBeInTheDocument()
    expect(screen.getByLabelText("Max domains")).toBeInTheDocument()
    expect(screen.getByLabelText("CPU millicores")).toBeInTheDocument()
    expect(screen.getByLabelText("Memory MB")).toBeInTheDocument()
    expect(screen.getByLabelText("Disk MB")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /Create plan/i })).toBeInTheDocument()
  })

  it("does not render Archive button in create mode", () => {
    render(<PlanForm />)
    expect(screen.queryByRole("button", { name: /Archive/i })).not.toBeInTheDocument()
  })
})

describe("PlanForm (edit mode)", () => {
  it("pre-fills fields with plan data", () => {
    render(<PlanForm plan={samplePlan} />)
    expect(screen.getByLabelText("Plan name")).toHaveValue("Starter Plan")
    expect(screen.getByLabelText("Price cents")).toHaveValue(999)
    expect(screen.getByLabelText("Max apps")).toHaveValue(3)
    expect(screen.getByLabelText("Max domains")).toHaveValue(5)
    expect(screen.getByRole("button", { name: /Save changes/i })).toBeInTheDocument()
  })

  it("shows Archive button for non-archived plans", () => {
    render(<PlanForm plan={samplePlan} />)
    expect(screen.getByRole("button", { name: /Archive/i })).toBeInTheDocument()
  })

  it("does not show Archive button for already-archived plans", () => {
    render(<PlanForm plan={{ ...samplePlan, is_archived: true }} />)
    expect(screen.queryByRole("button", { name: /Archive/i })).not.toBeInTheDocument()
  })

  it("shows Cancel button when onDone is provided", () => {
    render(<PlanForm plan={samplePlan} onDone={() => {}} />)
    expect(screen.getByRole("button", { name: /Cancel/i })).toBeInTheDocument()
  })
})
