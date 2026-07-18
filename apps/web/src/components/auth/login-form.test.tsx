import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

const push = vi.fn()
const refresh = vi.fn()
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, refresh }) }))

import { LoginForm } from "@/components/auth/login-form"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  push.mockClear()
  refresh.mockClear()
})

function fillAndSubmit() {
  fireEvent.change(screen.getByLabelText("Email"), { target: { value: "a@b.test" } })
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "secret" } })
  fireEvent.click(screen.getByRole("button", { name: /sign in/i }))
}

describe("LoginForm", () => {
  it("signs in and navigates to the returned next path", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ next: "/projects" }), { status: 200 }),
      ),
    )
    render(<LoginForm nextPath="/projects" />)
    fillAndSubmit()

    await waitFor(() => expect(push).toHaveBeenCalledWith("/projects"))
    expect(refresh).toHaveBeenCalled()
  })

  it("announces a failed login via an alert", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ error: "Invalid credentials." }), { status: 401 }),
      ),
    )
    render(<LoginForm />)
    fillAndSubmit()

    const alert = await screen.findByRole("alert")
    expect(alert.textContent).toContain("Invalid credentials.")
    expect(push).not.toHaveBeenCalled()
  })

  it("reports an unreachable auth service", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network down")))
    render(<LoginForm />)
    fillAndSubmit()

    const alert = await screen.findByRole("alert")
    expect(alert.textContent).toMatch(/unable to reach/i)
  })

  it("toggles password visibility", () => {
    render(<LoginForm />)
    const toggle = screen.getByRole("button", { name: /show password/i })
    expect(screen.getByLabelText("Password")).toHaveAttribute("type", "password")
    fireEvent.click(toggle)
    expect(screen.getByLabelText("Password")).toHaveAttribute("type", "text")
    expect(screen.getByRole("button", { name: /hide password/i })).toHaveAttribute(
      "aria-pressed",
      "true",
    )
  })
})
