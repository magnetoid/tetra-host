import { cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {}, refresh: () => {} }) }))

import { NotificationsManager } from "@/components/account/notifications-manager"
import type { NotificationChannelSummary } from "@/lib/types"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const CHANNEL: NotificationChannelSummary = {
  id: "n1",
  name: "team-slack",
  url: "https://hooks.slack.com/services/abc",
  events: "*",
  enabled: true,
  created_at: "2026-07-19T00:00:00Z",
  last_delivered_at: "",
  last_status: "ok",
}

describe("NotificationsManager", () => {
  it("lists channels with last status and the create form", () => {
    render(<NotificationsManager channels={[CHANNEL]} />)
    expect(screen.getByText("team-slack")).toBeInTheDocument()
    expect(screen.getByText("ok")).toBeInTheDocument()
    expect(screen.getByLabelText("Channel name")).toBeInTheDocument()
    expect(screen.getByLabelText("Webhook URL")).toBeInTheDocument()
  })

  it("creates a channel and reveals the signing secret once", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ ...CHANNEL, id: "n2", secret: "whsec_topsecret" }),
      }),
    )
    const user = userEvent.setup()
    render(<NotificationsManager channels={[]} />)
    await user.type(screen.getByLabelText("Channel name"), "ci")
    await user.type(screen.getByLabelText("Webhook URL"), "https://example.com/hook")
    await user.click(screen.getByRole("button", { name: /add channel/i }))
    expect(await screen.findByText("whsec_topsecret")).toBeInTheDocument()
    expect(screen.getByText(/shown only once/i)).toBeInTheDocument()
  })

  it("shows the result of a test send", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true, status: "ok" }) }),
    )
    const user = userEvent.setup()
    render(<NotificationsManager channels={[CHANNEL]} />)
    await user.click(screen.getByRole("button", { name: /test/i }))
    expect(await screen.findByText(/test: ok/i)).toBeInTheDocument()
  })
})
