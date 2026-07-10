import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: () => {} }) }))

import { SSOSettings } from "@/components/sso/sso-settings"
import type { SSOConfig } from "@/lib/types"

afterEach(() => cleanup())

const CONFIGURED: SSOConfig = {
  configured: true,
  enabled: true,
  provider_label: "Acme SSO",
  issuer: "https://idp.acme.test",
  client_id: "client-abc",
  has_secret: true,
  allowed_domains: "acme.com",
  default_role: "member",
}

describe("SSOSettings", () => {
  it("renders the config form with an enabled badge and a stored-secret hint", () => {
    render(<SSOSettings config={CONFIGURED} tenantSlug="acme" origin="https://console.test" />)
    expect(screen.getByLabelText("Issuer URL")).toHaveValue("https://idp.acme.test")
    expect(screen.getByLabelText("Client ID")).toHaveValue("client-abc")
    expect(screen.getByText("enabled")).toBeInTheDocument()
    // Secret input is present but empty (never hydrated from the server).
    expect(screen.getByLabelText("Client secret")).toHaveValue("")
    expect(screen.getByText(/leave blank to keep/i)).toBeInTheDocument()
  })

  it("shows the off badge and no remove button when unconfigured", () => {
    render(
      <SSOSettings
        config={{
          configured: false,
          enabled: false,
          provider_label: "OpenID Connect",
          issuer: "",
          client_id: "",
          has_secret: false,
          allowed_domains: "",
          default_role: "member",
        }}
        tenantSlug="acme"
        origin="https://console.test"
      />,
    )
    expect(screen.getByText("off")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /remove config/i })).not.toBeInTheDocument()
  })
})
