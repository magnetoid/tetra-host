import { describe, expect, it } from "vitest"

import { classifyDeploy, computeDeployStats, isDeploymentActive } from "@/lib/deploy-stats"
import type { ProjectDeploymentRecord } from "@/lib/types"

describe("isDeploymentActive", () => {
  it("is true while building/queued, false when finished or failed", () => {
    expect(isDeploymentActive("in_progress")).toBe(true)
    expect(isDeploymentActive("queued")).toBe(true)
    expect(isDeploymentActive("building")).toBe(true)
    expect(isDeploymentActive("finished")).toBe(false)
    expect(isDeploymentActive("failed")).toBe(false)
    expect(isDeploymentActive("")).toBe(false)
  })
})

function dep(status: string, created_at: string, id = created_at): ProjectDeploymentRecord {
  return { id, status, created_at, updated_at: created_at, commit: "abc", branch: "main" }
}

describe("classifyDeploy", () => {
  it("maps statuses to outcomes", () => {
    expect(classifyDeploy("finished")).toBe("succeeded")
    expect(classifyDeploy("success")).toBe("succeeded")
    expect(classifyDeploy("failed")).toBe("failed")
    expect(classifyDeploy("error")).toBe("failed")
    expect(classifyDeploy("cancelled")).toBe("failed")
    expect(classifyDeploy("in_progress")).toBe("running")
    expect(classifyDeploy("queued")).toBe("running")
    expect(classifyDeploy("weird-unknown")).toBe("running")
  })
})

describe("computeDeployStats", () => {
  it("counts outcomes, success rate over finished, and last deploy", () => {
    const stats = computeDeployStats(
      [
        dep("finished", "2026-07-10T10:00:00Z"),
        dep("finished", "2026-07-09T10:00:00Z"),
        dep("failed", "2026-07-08T10:00:00Z"),
        dep("in_progress", "2026-07-10T12:00:00Z"),
      ],
      { now: new Date("2026-07-10T23:00:00Z") },
    )
    expect(stats.total).toBe(4)
    expect(stats.succeeded).toBe(2)
    expect(stats.failed).toBe(1)
    expect(stats.running).toBe(1)
    expect(stats.successRate).toBe(67) // 2 / (2+1) finished
    expect(stats.lastDeployAt).toBe("2026-07-10T12:00:00Z")
  })

  it("fills a continuous 14-day activity window ending today", () => {
    const stats = computeDeployStats([dep("finished", "2026-07-10T10:00:00Z")], {
      now: new Date("2026-07-10T23:00:00Z"),
      windowDays: 14,
    })
    expect(stats.perDay).toHaveLength(14)
    expect(stats.perDay[13]).toEqual({ date: "07-10", deploys: 1 })
    expect(stats.perDay[0].deploys).toBe(0)
  })

  it("is safe with no deployments", () => {
    const stats = computeDeployStats([], { now: new Date("2026-07-10T00:00:00Z") })
    expect(stats.total).toBe(0)
    expect(stats.successRate).toBe(0)
    expect(stats.lastDeployAt).toBe("")
    expect(stats.perDay).toHaveLength(14)
  })
})
