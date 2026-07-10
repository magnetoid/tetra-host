import { describe, expect, it } from "vitest"

import { capabilitiesFor, unifyCoolify, unifyNative } from "@/lib/deployments"
import type { DeploymentRecord, ProjectDeploymentRecord } from "@/lib/types"

const NATIVE: DeploymentRecord = {
  id: "d1", project: "blog", status: "ready", git_url: "https://github.com/x/y",
  ref: "main", builder: "nixpacks", image: "tetra-blog:abc", commit: "abc123", port: 3000,
  domain: "blog.test", log: "", error: "", created_at: "2026-07-02T00:00:00",
}

describe("unified deployment model", () => {
  it("maps a native git build → source=git with rollback + logs, no redeploy", () => {
    const d = unifyNative(NATIVE)
    expect(d.source).toBe("git")
    const caps = capabilitiesFor(d)
    expect(caps).toMatchObject({ rollback: true, redeploy: false, logs: true, explain: false })
  })

  it("maps a marketplace app install → source=app, no rollback/redeploy", () => {
    const d = unifyNative({ ...NATIVE, builder: "app" })
    expect(d.source).toBe("app")
    expect(capabilitiesFor(d)).toMatchObject({ rollback: false, redeploy: false, logs: true })
  })

  it("does not offer rollback for a git build that has not produced an image yet", () => {
    const d = unifyNative({ ...NATIVE, status: "building", image: "" })
    expect(capabilitiesFor(d).rollback).toBe(false)
  })

  it("offers AI-explain only when a git build has an error", () => {
    expect(capabilitiesFor(unifyNative({ ...NATIVE, status: "error", error: "boom" })).explain).toBe(true)
    expect(capabilitiesFor(unifyNative(NATIVE)).explain).toBe(false)
  })

  it("maps a Coolify deployment → source=coolify with redeploy + logs, no rollback", () => {
    const record: ProjectDeploymentRecord = {
      id: "c1", status: "running", created_at: "2026-07-02T00:00:00",
      updated_at: "2026-07-02T00:00:00", commit: "deadbeef", branch: "main",
    }
    const d = unifyCoolify(record, "my-app")
    expect(d).toMatchObject({ source: "coolify", project: "my-app", branch: "main" })
    expect(capabilitiesFor(d)).toMatchObject({ rollback: false, redeploy: true, logs: true })
  })
})
