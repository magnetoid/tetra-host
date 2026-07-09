import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: () => {} }) }))

import { AiReseller } from "@/components/marketplace/ai-reseller"
import type { AiKey, AiModel } from "@/lib/types"

const models: AiModel[] = [
  { id: "openai/gpt-5", name: "GPT-5", context_length: 400000, prompt_price: "0.000005", completion_price: "0.00001" },
]
const keys: AiKey[] = [
  { hash: "h1", label: "acme", name: "acme", limit: 25, usage: 3, disabled: false },
]

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe("AiReseller", () => {
  it("renders the provision form, existing keys, and the model catalog", () => {
    render(<AiReseller models={models} keys={keys} />)
    expect(screen.getByLabelText("Key label")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /Provision/i })).toBeInTheDocument()
    expect(screen.getByText("acme")).toBeInTheDocument()
    expect(screen.getByText("GPT-5")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /Revoke/i })).toBeInTheDocument()
  })

  it("POSTs to /ai/keys and surfaces the one-time secret", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ key: "sk-or-secret", hash: "h9", label: "acme", limit: 25 }),
    })
    vi.stubGlobal("fetch", fetchMock)
    render(<AiReseller models={models} keys={keys} />)
    fireEvent.change(screen.getByLabelText("Key label"), { target: { value: "acme" } })
    fireEvent.change(screen.getByLabelText("Spend cap"), { target: { value: "25" } })
    fireEvent.click(screen.getByRole("button", { name: /Provision/i }))

    await waitFor(() => expect(screen.getByText("sk-or-secret")).toBeInTheDocument())
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe("/api/proxy/ai/keys")
    expect(init.method).toBe("POST")
    expect(JSON.parse(init.body)).toMatchObject({ label: "acme", limit: 25 })
  })
})
