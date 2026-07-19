import { cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {}, refresh: () => {} }) }))

import { ApiTokensManager } from "@/components/account/api-tokens-manager"
import type { ApiTokenSummary } from "@/lib/types"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const TOKEN: ApiTokenSummary = {
  id: "t1",
  name: "laptop",
  scope: "full",
  prefix: "tetra_ab12cd34",
  created_at: "2026-07-19T00:00:00Z",
  last_used_at: "",
  expires_at: "",
}

describe("ApiTokensManager", () => {
  it("lists tokens and the create form", () => {
    render(<ApiTokensManager tokens={[TOKEN]} />)
    expect(screen.getByText("laptop")).toBeInTheDocument()
    expect(screen.getByText(/tetra_ab12cd34/)).toBeInTheDocument()
    expect(screen.getByLabelText("Token name")).toBeInTheDocument()
    expect(screen.getByLabelText("Read-only token")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /create token/i })).toBeInTheDocument()
  })

  it("badges a read-only token", () => {
    render(<ApiTokensManager tokens={[{ ...TOKEN, scope: "read" }]} />)
    expect(screen.getByText("read-only")).toBeInTheDocument()
  })

  it("sends read_only when the box is checked", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ...TOKEN, id: "t2", scope: "read", token: "tetra_ro" }),
    })
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()
    render(<ApiTokensManager tokens={[]} />)
    await user.type(screen.getByLabelText("Token name"), "ci")
    await user.click(screen.getByLabelText("Read-only token"))
    await user.click(screen.getByRole("button", { name: /create token/i }))
    const body = JSON.parse(fetchMock.mock.calls[0][1].body)
    expect(body).toEqual({ name: "ci", read_only: true })
  })

  it("reveals the plaintext secret once after creating", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          id: "t2",
          name: "ci",
          prefix: "tetra_zz99",
          created_at: "2026-07-19T00:00:00Z",
          last_used_at: "",
          expires_at: "",
          token: "tetra_full_secret_value",
        }),
      }),
    )
    const user = userEvent.setup()
    render(<ApiTokensManager tokens={[]} />)

    await user.type(screen.getByLabelText("Token name"), "ci")
    await user.click(screen.getByRole("button", { name: /create token/i }))

    expect(await screen.findByText("tetra_full_secret_value")).toBeInTheDocument()
    expect(screen.getByText(/shown only once/i)).toBeInTheDocument()
  })

  it("surfaces an API error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, json: async () => ({ detail: "Could not create token." }) }),
    )
    const user = userEvent.setup()
    render(<ApiTokensManager tokens={[]} />)
    await user.type(screen.getByLabelText("Token name"), "x")
    await user.click(screen.getByRole("button", { name: /create token/i }))
    expect(await screen.findByText(/could not create token/i)).toBeInTheDocument()
  })
})
