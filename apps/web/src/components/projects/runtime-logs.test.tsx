import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { RuntimeLogs } from "@/components/projects/runtime-logs"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe("RuntimeLogs", () => {
  it("loads and renders runtime output from the proxy", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ logs: "hello runtime world" }),
    })
    vi.stubGlobal("fetch", fetchMock)

    render(<RuntimeLogs projectId="proj-1" />)

    expect(await screen.findByText(/hello runtime world/)).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith("/api/proxy/projects/proj-1/logs?lines=200")
  })

  it("shows a placeholder when there is no output", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: async () => ({ logs: "" }) }),
    )

    render(<RuntimeLogs projectId="proj-1" />)

    expect(await screen.findByText(/no runtime output/i)).toBeInTheDocument()
  })

  it("surfaces an error when the request fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 502,
        json: async () => ({ detail: "Logs unavailable" }),
      }),
    )

    render(<RuntimeLogs projectId="proj-1" />)

    expect(await screen.findByText(/logs unavailable/i)).toBeInTheDocument()
  })
})
