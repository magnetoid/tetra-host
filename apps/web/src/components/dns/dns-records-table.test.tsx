import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: () => {} }) }))

import { DnsRecordsTable } from "@/components/dns/dns-records-table"
import type { DNSRecord } from "@/lib/types"

const records: DNSRecord[] = [
  { id: "r1", type: "A", name: "app.test", content: "1.2.3.4", ttl: 1, proxied: true },
  { id: "r2", type: "MX", name: "mailhost", content: "mx.provider.io", ttl: 1, proxied: false, priority: 10 },
]

afterEach(() => cleanup())

describe("DnsRecordsTable", () => {
  it("shows proxy status and filters rows by search", () => {
    render(<DnsRecordsTable zoneId="z1" records={records} />)
    expect(screen.getByText("app.test")).toBeInTheDocument()
    expect(screen.getByText(/Proxied/)).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText("Search records"), { target: { value: "mailhost" } })
    expect(screen.queryByText("app.test")).not.toBeInTheDocument()
    expect(screen.getByText("mailhost")).toBeInTheDocument()
  })

  it("opens an inline edit form when Edit is clicked", () => {
    render(<DnsRecordsTable zoneId="z1" records={records} />)
    fireEvent.click(screen.getAllByText("Edit")[0])
    expect(screen.getByText("Edit DNS record")).toBeInTheDocument()
  })
})
