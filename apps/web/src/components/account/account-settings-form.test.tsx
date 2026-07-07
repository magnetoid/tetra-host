import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: () => {} }) }))

import { AccountSettingsForm } from "@/components/account/account-settings-form"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe("AccountSettingsForm", () => {
  it("pre-fills profile fields and renders both forms", () => {
    render(<AccountSettingsForm fullName="Ada Admin" email="ada@example.com" />)
    expect(screen.getByLabelText("Full name")).toHaveValue("Ada Admin")
    expect(screen.getByLabelText("Email")).toHaveValue("ada@example.com")
    expect(screen.getByRole("button", { name: /Save profile/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /Change password/i })).toBeInTheDocument()
  })

  it("PATCHes /account on profile save", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) })
    vi.stubGlobal("fetch", fetchMock)
    render(<AccountSettingsForm fullName="Ada" email="ada@example.com" />)
    fireEvent.change(screen.getByLabelText("Full name"), { target: { value: "Ada B" } })
    fireEvent.click(screen.getByRole("button", { name: /Save profile/i }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe("/api/proxy/account")
    expect(init.method).toBe("PATCH")
    expect(JSON.parse(init.body)).toMatchObject({ full_name: "Ada B", email: "ada@example.com" })
  })

  it("blocks the password change when confirmation does not match", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) })
    vi.stubGlobal("fetch", fetchMock)
    render(<AccountSettingsForm fullName="Ada" email="ada@example.com" />)
    fireEvent.change(screen.getByLabelText("Current password"), { target: { value: "oldsecret12" } })
    fireEvent.change(screen.getByLabelText("New password"), { target: { value: "newsecret123" } })
    fireEvent.change(screen.getByLabelText("Confirm new password"), { target: { value: "mismatch1234" } })
    fireEvent.click(screen.getByRole("button", { name: /Change password/i }))
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/do not match/i))
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it("POSTs /account/password on a valid change", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true }) })
    vi.stubGlobal("fetch", fetchMock)
    render(<AccountSettingsForm fullName="Ada" email="ada@example.com" />)
    fireEvent.change(screen.getByLabelText("Current password"), { target: { value: "oldsecret12" } })
    fireEvent.change(screen.getByLabelText("New password"), { target: { value: "newsecret123" } })
    fireEvent.change(screen.getByLabelText("Confirm new password"), { target: { value: "newsecret123" } })
    fireEvent.click(screen.getByRole("button", { name: /Change password/i }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe("/api/proxy/account/password")
    expect(init.method).toBe("POST")
    expect(JSON.parse(init.body)).toMatchObject({
      current_password: "oldsecret12",
      new_password: "newsecret123",
    })
  })
})
