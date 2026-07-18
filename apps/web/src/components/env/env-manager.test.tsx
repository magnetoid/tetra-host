import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {}, refresh: () => {} }) }))

import { EnvManager, type EnvRow } from "@/components/env/env-manager"

afterEach(() => cleanup())

const DEPLOY_VARS: EnvRow[] = [
  { key: "NODE_ENV", value: "production", is_secret: false },
  { key: "API_KEY", value: "sk-secret", is_secret: true },
]

const APP_VARS: EnvRow[] = [
  { uuid: "u1", key: "DATABASE_URL", value: "postgres://real" },
  { uuid: "u2", key: "REDIS_URL", value: "redis://real" },
]

describe("EnvManager (deploy target)", () => {
  it("renders vars, masks secrets, shows the secret chip and form", () => {
    render(<EnvManager target={{ kind: "deploy", project: "blog" }} vars={DEPLOY_VARS} />)
    expect(screen.getByText("NODE_ENV")).toBeInTheDocument()
    expect(screen.getByText("production")).toBeInTheDocument()
    expect(screen.queryByText("sk-secret")).not.toBeInTheDocument()
    expect(screen.getByText("secret")).toBeInTheDocument()
    expect(screen.getByLabelText("Variable key")).toBeInTheDocument()
    expect(screen.getByText("Secret")).toBeInTheDocument()
  })

  it("shows the empty state without vars", () => {
    render(<EnvManager target={{ kind: "deploy", project: "blog" }} vars={[]} />)
    expect(screen.getByText(/no environment variables/i)).toBeInTheDocument()
  })
})

describe("EnvManager (app target)", () => {
  it("masks all values by default with a reveal toggle and no secret checkbox", () => {
    render(<EnvManager target={{ kind: "app", applicationId: "abc" }} vars={APP_VARS} />)
    expect(screen.getByText("DATABASE_URL")).toBeInTheDocument()
    expect(screen.queryByText("postgres://real")).not.toBeInTheDocument()
    expect(screen.getByText("Reveal values")).toBeInTheDocument()
    expect(screen.queryByText("Secret")).not.toBeInTheDocument()
  })
})
