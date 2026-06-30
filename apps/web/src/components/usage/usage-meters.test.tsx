import { afterEach, describe, expect, it } from "vitest"
import { cleanup, render, screen } from "@testing-library/react"

import { UsageMeters } from "@/components/usage/usage-meters"
import type { Usage } from "@/lib/types"

const sampleUsage: Usage = {
  plan_key: "starter",
  apps_used: 2,
  apps_limit: 5,
  cpu_millicores_used: 250,
  cpu_millicores_limit: 1000,
  mem_mb_used: 128,
  mem_mb_limit: 512,
  disk_mb_used: 1024,
  disk_mb_limit: 10240,
  domains_used: 3,
  domains_limit: 10,
  enforced: ["apps"],
}

afterEach(() => cleanup())

describe("UsageMeters", () => {
  it("renders all five dimension labels", () => {
    render(<UsageMeters usage={sampleUsage} />)
    expect(screen.getByText("Apps")).toBeInTheDocument()
    expect(screen.getByText("CPU")).toBeInTheDocument()
    expect(screen.getByText("Memory")).toBeInTheDocument()
    expect(screen.getByText("Disk")).toBeInTheDocument()
    expect(screen.getByText("Domains")).toBeInTheDocument()
  })

  it("shows used / limit text for the apps meter", () => {
    render(<UsageMeters usage={sampleUsage} />)
    expect(screen.getByText("2 / 5")).toBeInTheDocument()
  })

  it("shows the enforced badge on the apps meter", () => {
    render(<UsageMeters usage={sampleUsage} />)
    expect(screen.getByText("enforced")).toBeInTheDocument()
  })

  it("shows advisory badges for non-enforced dimensions", () => {
    render(<UsageMeters usage={sampleUsage} />)
    const advisoryBadges = screen.getAllByText("advisory — not yet enforced")
    // cpu, mem, disk, domains — 4 advisory dimensions
    expect(advisoryBadges).toHaveLength(4)
  })

  it("displays the plan key", () => {
    render(<UsageMeters usage={sampleUsage} />)
    expect(screen.getByText("starter")).toBeInTheDocument()
  })

  it("renders the section heading", () => {
    render(<UsageMeters usage={sampleUsage} />)
    expect(screen.getByText("Quota usage")).toBeInTheDocument()
  })

  it("renders cpu used/limit with unit", () => {
    render(<UsageMeters usage={sampleUsage} />)
    expect(screen.getByText("250 m / 1,000 m")).toBeInTheDocument()
  })

  it("renders memory used/limit in MB", () => {
    render(<UsageMeters usage={sampleUsage} />)
    expect(screen.getByText("128 MB / 512 MB")).toBeInTheDocument()
  })
})
