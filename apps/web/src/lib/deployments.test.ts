import { describe, expect, it } from "vitest"

import { capabilitiesFor, unifyNative } from "@/lib/deployments"
import type { DeploymentRecord } from "@/lib/types"

const NATIVE: DeploymentRecord = {
  id: "d1", project: "blog", status: "ready", git_url: "https://github.com/x/y",
  ref: "main", builder: "nixpacks", image: "tetra-blog:abc", commit: "abc123", port: 3000,
  domain: "blog.test", log: "", error: "", created_at: "2026-07-02T00:00:00",
}

describe("unified deployment model", () => {
  it("maps a native git build → source=git with rollback + logs", () => {
    const d = unifyNative(NATIVE)
    expect(d.source).toBe("git")
    const caps = capabilitiesFor(d)
    expect(caps).toMatchObject({ rollback: true, logs: true, explain: false })
  })

  it("maps a marketplace app install → source=app, no rollback", () => {
    const d = unifyNative({ ...NATIVE, builder: "app" })
    expect(d.source).toBe("app")
    expect(capabilitiesFor(d)).toMatchObject({ rollback: false, logs: true })
  })

  it("does not offer rollback for a git build that has not produced an image yet", () => {
    const d = unifyNative({ ...NATIVE, status: "building", image: "" })
    expect(capabilitiesFor(d).rollback).toBe(false)
  })

  it("offers cancel only while a git build is queued or building", () => {
    expect(capabilitiesFor(unifyNative({ ...NATIVE, status: "queued", image: "" })).cancel).toBe(true)
    expect(capabilitiesFor(unifyNative({ ...NATIVE, status: "building", image: "" })).cancel).toBe(true)
    expect(capabilitiesFor(unifyNative(NATIVE)).cancel).toBe(false)
    expect(capabilitiesFor(unifyNative({ ...NATIVE, status: "cancelled" })).cancel).toBe(false)
    expect(capabilitiesFor(unifyNative({ ...NATIVE, builder: "app", status: "building" })).cancel).toBe(false)
  })

  it("offers AI-explain only when a git build has an error", () => {
    expect(capabilitiesFor(unifyNative({ ...NATIVE, status: "error", error: "boom" })).explain).toBe(true)
    expect(capabilitiesFor(unifyNative(NATIVE)).explain).toBe(false)
  })
})
