import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

vi.mock("next/navigation", () => ({ usePathname: () => "/domains/acme.test/web" }))

import { DomainTabs } from "@/components/domains/domain-tabs"
import { DomainsHub } from "@/components/domains/domains-hub"
import { defaultDomainTab, findDomain, isUnder } from "@/lib/domains"
import type { DomainOverviewEntry } from "@/lib/types"

afterEach(() => cleanup())

const ACME: DomainOverviewEntry = {
  name: "acme.test",
  zone: { id: "z1", status: "active", paused: false },
  mail: [{ domain_name: "acme.test", mailboxes: 3, aliases: 0, active: true }],
  hostnames: [
    { id: "h1", hostname: "www.acme.test", status: "verified", stack: "web", service: null },
    { id: "h2", hostname: "api.acme.test", status: "pending", stack: "api", service: null },
  ],
}
const SOLO: DomainOverviewEntry = { name: "solo.test", zone: null, mail: [], hostnames: [] }

describe("domain helpers", () => {
  it("matches the apex and its subdomains only", () => {
    expect(isUnder("acme.test", "acme.test")).toBe(true)
    expect(isUnder("WWW.acme.test.", "acme.test")).toBe(true)
    expect(isUnder("notacme.test", "acme.test")).toBe(false)
  })

  it("finds a domain by apex or by a name under it", () => {
    expect(findDomain([ACME, SOLO], "acme.test")).toBe(ACME)
    expect(findDomain([ACME, SOLO], "mail.acme.test")).toBe(ACME)
    expect(findDomain([ACME, SOLO], "other.test")).toBeUndefined()
  })

  it("opens on DNS only when the zone is on Cloudflare", () => {
    expect(defaultDomainTab(ACME)).toBe("dns")
    expect(defaultDomainTab(SOLO)).toBe("web")
  })
})

describe("DomainsHub", () => {
  it("summarises DNS, web and mail per domain", () => {
    render(<DomainsHub domains={[ACME, SOLO]} />)
    expect(screen.getByRole("link", { name: "acme.test" })).toHaveAttribute("href", "/domains/acme.test")
    expect(screen.getByText(/2 hostnames/)).toBeInTheDocument()
    expect(screen.getByText(/1 pending/)).toBeInTheDocument()
    expect(screen.getByText("3 mailboxes")).toBeInTheDocument()
    expect(screen.getByText("Not on Cloudflare")).toBeInTheDocument()
    expect(screen.getByText("Off")).toBeInTheDocument()
  })

  it("shows an empty state without domains", () => {
    render(<DomainsHub domains={[]} />)
    expect(screen.getByText("No domains yet")).toBeInTheDocument()
  })
})

describe("DomainTabs", () => {
  it("marks the current tab", () => {
    render(<DomainTabs name="acme.test" counts={{ web: 2 }} />)
    expect(screen.getByRole("tab", { name: /web/i })).toHaveAttribute("aria-selected", "true")
    expect(screen.getByRole("tab", { name: /dns/i })).toHaveAttribute("href", "/domains/acme.test/dns")
  })
})
