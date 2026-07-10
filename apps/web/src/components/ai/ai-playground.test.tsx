import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { AiPlayground } from "@/components/ai/ai-playground"
import type { AiModel, AiStatus } from "@/lib/types"

afterEach(() => cleanup())

const MODELS: AiModel[] = [
  { id: "openai/gpt-4o-mini", name: "GPT-4o mini", context_length: 128000, prompt_price: "0", completion_price: "0" },
]
const GATEWAY: AiStatus = { mode: "gateway", configured: true, platform_credit_usd: 10, platform_used_usd: 0 }

describe("AiPlayground", () => {
  it("renders the model picker + prompt when funded", () => {
    render(<AiPlayground models={MODELS} status={GATEWAY} initialBalanceUsd={5} />)
    expect(screen.getByLabelText("Model")).toHaveValue("openai/gpt-4o-mini")
    expect(screen.getByLabelText("Prompt")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /send/i })).not.toBeDisabled
  })

  it("nudges a top-up and disables send when out of credit", () => {
    render(<AiPlayground models={MODELS} status={GATEWAY} initialBalanceUsd={0} />)
    expect(screen.getByText(/no AI credit/i)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /send/i })).toBeDisabled()
  })

  it("explains when the platform runs per-tenant keys instead of the gateway", () => {
    render(
      <AiPlayground
        models={MODELS}
        status={{ ...GATEWAY, mode: "keys" }}
        initialBalanceUsd={5}
      />,
    )
    expect(screen.getByText(/per-tenant AI keys/i)).toBeInTheDocument()
  })
})
