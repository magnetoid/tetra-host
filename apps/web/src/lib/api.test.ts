import { afterEach, describe, expect, it, vi } from "vitest"

import { proxyBackendRequest } from "@/lib/api"

afterEach(() => vi.unstubAllGlobals())

function backendAnswers(status: number, body: string | null) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(body, { status, headers: { "content-type": "application/json" } })),
  )
}

describe("proxyBackendRequest", () => {
  it("passes a bodyless 204 through instead of failing", async () => {
    backendAnswers(204, null)
    const res = await proxyBackendRequest(
      "/teams/acme/projects/shop",
      new Request("http://localhost/api/proxy/teams/acme/projects/shop", { method: "DELETE" }),
      "token",
    )
    expect(res.status).toBe(204)
    expect(await res.text()).toBe("")
  })

  it("keeps the body and status of ordinary responses", async () => {
    backendAnswers(201, '{"slug":"shop"}')
    const res = await proxyBackendRequest(
      "/teams/acme/projects",
      new Request("http://localhost/api/proxy/teams/acme/projects", { method: "POST", body: "{}" }),
    )
    expect(res.status).toBe(201)
    expect(await res.json()).toEqual({ slug: "shop" })
  })
})
