import { cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {}, refresh: () => {} }) }))

import { TwoFactorManager } from "@/components/account/two-factor-manager"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe("TwoFactorManager", () => {
  it("prompts to enable when 2FA is off", () => {
    render(<TwoFactorManager status={{ enabled: false, backup_codes_remaining: 0 }} />)
    expect(screen.getByRole("button", { name: /enable 2fa/i })).toBeInTheDocument()
  })

  it("shows enabled state with remaining backup codes and a disable form", () => {
    render(<TwoFactorManager status={{ enabled: true, backup_codes_remaining: 7 }} />)
    expect(screen.getByText(/enabled/i)).toBeInTheDocument()
    expect(screen.getByText(/7 backup codes remaining/i)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /disable 2fa/i })).toBeInTheDocument()
  })

  it("runs the setup → verify → backup-codes flow", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ secret: "ABCD2345EFGH6789", otpauth_uri: "otpauth://totp/x?secret=ABCD" }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ backup_codes: ["11111-22222", "33333-44444"] }),
      })
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()
    render(<TwoFactorManager status={{ enabled: false, backup_codes_remaining: 0 }} />)

    await user.click(screen.getByRole("button", { name: /enable 2fa/i }))
    // Setup key revealed (grouped into 4-char blocks).
    expect(await screen.findByText(/ABCD 2345 EFGH 6789/)).toBeInTheDocument()
    expect(fetchMock.mock.calls[0][0]).toBe("/api/proxy/account/2fa/setup")

    await user.type(screen.getByLabelText("Verification code"), "123456")
    await user.click(screen.getByRole("button", { name: /verify & enable/i }))

    expect(await screen.findByText("11111-22222")).toBeInTheDocument()
    expect(screen.getByText(/shown only once/i)).toBeInTheDocument()
    const enableBody = JSON.parse(fetchMock.mock.calls[1][1].body)
    expect(enableBody).toEqual({ code: "123456" })
  })

  it("surfaces a rejected code", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce({ ok: true, json: async () => ({ secret: "AB", otpauth_uri: "otpauth://x" }) })
        .mockResolvedValueOnce({ ok: false, json: async () => ({ detail: "That code was not accepted." }) }),
    )
    const user = userEvent.setup()
    render(<TwoFactorManager status={{ enabled: false, backup_codes_remaining: 0 }} />)
    await user.click(screen.getByRole("button", { name: /enable 2fa/i }))
    await user.type(await screen.findByLabelText("Verification code"), "000000")
    await user.click(screen.getByRole("button", { name: /verify & enable/i }))
    expect(await screen.findByText(/that code was not accepted/i)).toBeInTheDocument()
  })
})
