import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {}, refresh: () => {} }) }))

import { DomainsManager } from "@/components/domains/domains-manager"
import type { DomainRecord, InstalledApp } from "@/lib/types"

afterEach(() => cleanup())

const APPS: InstalledApp[] = [
  { project: "blog", name: "Blog", template: "wordpress", status: "running", domain: "" },
]

const PENDING: DomainRecord = {
  id: "d1", project: "blog", hostname: "www.example.com", status: "pending",
  txt_name: "_tetra-challenge.www.example.com", txt_value: "tok123",
  cname_target: "edge.cloud-industry.com",
}

describe("DomainsManager", () => {
  it("shows DNS instructions and a Verify button for pending domains", () => {
    render(<DomainsManager domains={[PENDING]} apps={APPS} />)
    expect(screen.getByText("www.example.com")).toBeInTheDocument()
    expect(screen.getByText(/_tetra-challenge\.www\.example\.com/)).toBeInTheDocument()
    expect(screen.getByText(/edge\.cloud-industry\.com/)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /verify/i })).toBeInTheDocument()
  })

  it("hides Verify and instructions for verified domains", () => {
    render(<DomainsManager domains={[{ ...PENDING, status: "verified" }]} apps={APPS} />)
    expect(screen.queryByRole("button", { name: /verify/i })).not.toBeInTheDocument()
    expect(screen.getByText(/redeploy the app/i)).toBeInTheDocument()
  })

  it("renders the empty state and the add form", () => {
    render(<DomainsManager domains={[]} apps={APPS} />)
    expect(screen.getByText(/no custom domains yet/i)).toBeInTheDocument()
    expect(screen.getByLabelText("Domain")).toBeInTheDocument()
    expect(screen.getByLabelText("App")).toBeInTheDocument()
  })
})
