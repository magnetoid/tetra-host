import { cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {}, refresh: () => {} }) }))

import { DeployHooksManager } from "@/components/deploys/deploy-hooks-manager"
import type { DeployHook } from "@/lib/types"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const HOOK: DeployHook = {
  id: "h1", project: "blog", git_url: "https://github.com/x/y", ref: "main", port: 3000, enabled: true,
}

describe("DeployHooksManager", () => {
  it("lists hooks and the create form", () => {
    render(<DeployHooksManager hooks={[HOOK]} />)
    expect(screen.getByText("blog")).toBeInTheDocument()
    expect(screen.getByText("@main")).toBeInTheDocument()
    expect(screen.getByLabelText("Webhook app")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /create webhook/i })).toBeInTheDocument()
  })

  it("shows the one-time URL + secret after creating", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          id: "h2", project: "shop", ref: "main",
          url: "https://panel.test/api/v1/webhooks/github/h2", secret: "s3cr3t-once",
        }),
      }),
    )
    const user = userEvent.setup()
    render(<DeployHooksManager hooks={[]} />)
    await user.type(screen.getByLabelText("Webhook app"), "shop")
    await user.type(screen.getByLabelText("Webhook git repository"), "https://github.com/x/shop")
    await user.click(screen.getByRole("button", { name: /create webhook/i }))
    expect(await screen.findByText(/shown only once/i)).toBeInTheDocument()
    expect(screen.getByText(/s3cr3t-once/)).toBeInTheDocument()
    expect(screen.getByText(/webhooks\/github\/h2/)).toBeInTheDocument()
  })
})
