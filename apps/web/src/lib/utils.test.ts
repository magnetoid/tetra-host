import { describe, expect, it } from "vitest"

import { formatBytes, normalizeStatus, safeNextPath, statusTone } from "@/lib/utils"

describe("normalizeStatus", () => {
  const cases: Array<[string, string, boolean]> = [
    ["running:healthy", "Running", false],
    ["running:unhealthy", "Unhealthy", false],
    ["exited:unhealthy", "Stopped", false],
    ["0:unhealthy", "Stopped", false],
    ["restarting", "Deploying", true],
    ["in_progress", "Deploying", true],
    ["", "Unknown", false],
    ["unknown", "Unknown", false],
  ]
  it.each(cases)("maps %s → %s (pulse=%s)", (raw, label, pulse) => {
    const v = normalizeStatus(raw)
    expect(v.label).toBe(label)
    expect(v.pulse).toBe(pulse)
  })
})

describe("utils", () => {
  it("formats byte sizes", () => {
    expect(formatBytes(0)).toBe("0 B")
    expect(formatBytes(1536)).toBe("1.5 KB")
  })

  it("normalizes next paths", () => {
    expect(safeNextPath("/projects")).toBe("/projects")
    expect(safeNextPath("https://evil.test")).toBe("/dashboard")
  })

  it("maps status tones", () => {
    expect(statusTone("connected")).toBe("positive")
    expect(statusTone("unhealthy")).toBe("critical")
  })
})
