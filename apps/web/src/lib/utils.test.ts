import { describe, expect, it } from "vitest"

import { formatBytes, safeNextPath, statusTone } from "@/lib/utils"

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
