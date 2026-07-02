import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ComputePanel } from "@/components/apps/compute-panel"
import type { ComputeMetrics } from "@/lib/types"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const METRICS: ComputeMetrics = {
  project: "blog",
  cpu_percent: 12.5,
  mem_used_mb: 105,
  samples: [
    {
      name: "blog-app-1", cpu_percent: 12.5, mem_used_mb: 105, mem_limit_mb: 512,
      mem_percent: 20.5, net_rx_mb: 0.1, net_tx_mb: 0.2, pids: 7,
    },
  ],
}

describe("ComputePanel", () => {
  it("renders KPI totals and per-container bars", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => METRICS }))
    render(<ComputePanel project="blog" initial={METRICS} />)

    // Container name appears in the CPU + Memory bar lists.
    expect((await screen.findAllByText("blog-app-1")).length).toBeGreaterThan(0)
    expect(screen.getByText("CPU")).toBeInTheDocument()
    expect(screen.getByText("Memory")).toBeInTheDocument()
    expect(screen.getByText("Containers")).toBeInTheDocument()
  })

  it("shows an empty state when there are no running containers", () => {
    const empty: ComputeMetrics = { ...METRICS, samples: [] }
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => empty }))
    render(<ComputePanel project="blog" initial={empty} />)
    expect(screen.getByText(/no running containers/i)).toBeInTheDocument()
  })
})
