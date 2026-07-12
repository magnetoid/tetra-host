import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: () => {} }) }))
vi.mock("@fortawesome/react-fontawesome", () => ({ FontAwesomeIcon: () => null }))

import { BulkMailboxImport } from "@/components/mail/bulk-mailbox-import"

afterEach(cleanup)

const domains = [
  { domain_name: "example.com", mailboxes: 0, aliases: 0, quota_bytes: 0, active: true },
]

describe("BulkMailboxImport", () => {
  it("disables the create button until lines are entered, then counts them", () => {
    render(<BulkMailboxImport domains={domains} />)
    const button = screen.getByRole("button", { name: /create/i })
    expect(button).toBeDisabled()

    fireEvent.change(screen.getByLabelText("Mailboxes to import"), {
      target: { value: "marko,Marko T\nsupport\n\ninfo,Info" },
    })
    // 3 non-empty lines parsed (blank line ignored)
    expect(screen.getByRole("button", { name: /create 3 mailboxes/i })).toBeEnabled()
  })
})
