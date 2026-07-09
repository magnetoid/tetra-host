import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, render, screen, waitFor } from "@testing-library/react"

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: () => {} }) }))

import { CloudflareReseller } from "@/components/marketplace/cloudflare-reseller"
import type { DNSZoneRecord, ResellableService } from "@/lib/types"

const services: ResellableService[] = [
  { key: "argo", name: "Argo Smart Routing", category: "performance", activation: "toggle", rate_plan: "", description: "Fast paths." },
  { key: "waf_managed", name: "WAF Managed Rules", category: "security", activation: "plan", rate_plan: "pro", description: "Managed WAF." },
]
const zones: DNSZoneRecord[] = [
  { id: "z1", name: "acme.com", status: "active", account_name: "acme", paused: false },
]

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe("CloudflareReseller", () => {
  it("shows an empty state when the tenant has no zones", () => {
    render(<CloudflareReseller services={services} zones={[]} />)
    expect(screen.getByText(/No Cloudflare zones/i)).toBeInTheDocument()
  })

  it("loads plans for the selected zone and lists services by category", async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url.includes("/plans")) {
        return Promise.resolve({
          ok: true,
          json: async () => [
            { id: "pro", name: "Pro", price: 20, currency: "USD", frequency: "monthly", can_subscribe: true, is_subscribed: false },
          ],
        })
      }
      return Promise.resolve({ ok: true, json: async () => ({ rate_plan_id: "", state: "" }) })
    })
    vi.stubGlobal("fetch", fetchMock)

    render(<CloudflareReseller services={services} zones={zones} />)
    expect(screen.getByLabelText("Zone")).toBeInTheDocument()
    // service catalog rendered by category
    expect(screen.getByText("Argo Smart Routing")).toBeInTheDocument()
    expect(screen.getByText("WAF Managed Rules")).toBeInTheDocument()
    // plan loaded from the proxy on mount
    await waitFor(() => expect(screen.getByText("Pro")).toBeInTheDocument())
    expect(fetchMock).toHaveBeenCalledWith("/api/proxy/cloudflare/zones/z1/plans")
  })
})
