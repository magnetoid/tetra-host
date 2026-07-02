import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {}, refresh: () => {} }) }))

import { EnvManager } from "@/components/apps/env-manager"
import type { AppEnvVar } from "@/lib/types"

afterEach(() => cleanup())

const VARS: AppEnvVar[] = [
  { key: "NODE_ENV", value: "production", is_secret: false, is_build_time: false },
  { key: "API_KEY", value: "••••••", is_secret: true, is_build_time: false },
]

describe("EnvManager", () => {
  it("renders vars with masked secrets and the set form", () => {
    render(<EnvManager project="blog" vars={VARS} />)
    expect(screen.getByText("NODE_ENV")).toBeInTheDocument()
    expect(screen.getByText("production")).toBeInTheDocument()
    expect(screen.getByText("••••••")).toBeInTheDocument()
    expect(screen.getByText("secret")).toBeInTheDocument()
    expect(screen.getByLabelText("Key")).toBeInTheDocument()
    expect(screen.getByLabelText("Secret")).toBeInTheDocument()
  })

  it("shows the empty state without vars", () => {
    render(<EnvManager project="blog" vars={[]} />)
    expect(screen.getByText(/no environment variables/i)).toBeInTheDocument()
  })
})
