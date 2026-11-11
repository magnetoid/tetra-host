import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {}, refresh: () => {} }) }))

import { EnvManager, type EnvRow } from "@/components/env/env-manager"

afterEach(() => cleanup())

const DEPLOY_VARS: EnvRow[] = [
  { key: "NODE_ENV", value: "production", is_secret: false },
  { key: "API_KEY", value: "sk-secret", is_secret: true },
]

describe("EnvManager", () => {
  it("renders vars, masks secrets, shows the secret chip and form", () => {
    render(<EnvManager project="blog" vars={DEPLOY_VARS} />)
    expect(screen.getByText("NODE_ENV")).toBeInTheDocument()
    expect(screen.getByText("production")).toBeInTheDocument()
    expect(screen.queryByText("sk-secret")).not.toBeInTheDocument()
    expect(screen.getByText("secret")).toBeInTheDocument()
    expect(screen.getByLabelText("Variable key")).toBeInTheDocument()
    expect(screen.getByText("Secret")).toBeInTheDocument()
  })

  it("shows the empty state without vars", () => {
    render(<EnvManager project="blog" vars={[]} />)
    expect(screen.getByText(/no environment variables/i)).toBeInTheDocument()
  })
})
