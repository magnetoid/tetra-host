import { cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {}, refresh: () => {} }) }))

import { MonitorsManager } from "@/components/monitors/monitors-manager"
import type { UptimeMonitorSummary } from "@/lib/types"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const MONITOR: UptimeMonitorSummary = {
  id: "m1",
  name: "site",
  url: "https://example.com",
  enabled: true,
  status: "up",
  last_checked_at: "2026-07-19T00:00:00Z",
  last_latency_ms: 120,
  last_detail: "HTTP 200",
  created_at: "2026-07-19T00:00:00Z",
}

describe("MonitorsManager", () => {
  it("shows an empty state and the create form", () => {
    render(<MonitorsManager monitors={[]} />)
    expect(screen.getByText(/no monitors yet/i)).toBeInTheDocument()
    expect(screen.getByLabelText("Monitor name")).toBeInTheDocument()
    expect(screen.getByLabelText("Monitor URL")).toBeInTheDocument()
  })

  it("renders a monitor's status, latency, and actions", () => {
    render(<MonitorsManager monitors={[MONITOR]} />)
    expect(screen.getByText("site")).toBeInTheDocument()
    expect(screen.getByText("Up")).toBeInTheDocument()
    expect(screen.getByText(/120ms · HTTP 200/)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /check now/i })).toBeInTheDocument()
  })

  it("posts a new monitor", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ id: "m2" }) })
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()
    render(<MonitorsManager monitors={[]} />)
    await user.type(screen.getByLabelText("Monitor name"), "api")
    await user.type(screen.getByLabelText("Monitor URL"), "https://api.example.com")
    await user.click(screen.getByRole("button", { name: /add monitor/i }))
    expect(fetchMock).toHaveBeenCalledWith("/api/proxy/account/monitors", expect.anything())
    const body = JSON.parse(fetchMock.mock.calls[0][1].body)
    expect(body).toEqual({ name: "api", url: "https://api.example.com" })
  })
})
