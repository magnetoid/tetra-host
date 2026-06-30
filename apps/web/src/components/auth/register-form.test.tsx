import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, render, screen } from "@testing-library/react"

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {}, refresh: () => {} }) }))

import { RegisterForm } from "@/components/auth/register-form"

afterEach(() => cleanup())

describe("RegisterForm", () => {
  it("renders org name, email, password fields and submit button", () => {
    render(<RegisterForm />)
    expect(screen.getByLabelText("Organisation name")).toBeInTheDocument()
    expect(screen.getByLabelText("Email")).toBeInTheDocument()
    expect(screen.getByLabelText("Password")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /Create account/i })).toBeInTheDocument()
  })

  it("password field has minLength 10", () => {
    render(<RegisterForm />)
    const pwd = screen.getByLabelText("Password")
    expect(pwd).toHaveAttribute("minLength", "10")
  })

  it("submit button is not disabled by default", () => {
    render(<RegisterForm />)
    expect(screen.getByRole("button", { name: /Create account/i })).not.toBeDisabled()
  })
})
