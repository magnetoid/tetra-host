import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: () => {} }) }))
vi.mock("@fortawesome/react-fontawesome", () => ({ FontAwesomeIcon: () => null }))

import { MailManager } from "@/components/mail/mail-manager"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const domains = [
  { domain_name: "example.com", mailboxes: 2, aliases: 1, quota_bytes: 1024, active: true },
]
const mailboxes = [
  {
    username: "you@example.com",
    name: "You",
    domain: "example.com",
    quota_bytes: 1024,
    messages: 0,
    active: true,
  },
]

describe("MailManager", () => {
  it("offers app domains as quick picks, excluding ones that already have mail", () => {
    render(
      <MailManager domains={domains} mailboxes={mailboxes} appDomains={["shop.io", "example.com"]} />,
    )
    expect(screen.getByRole("button", { name: /add domain/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "shop.io" })).toBeInTheDocument()
    // example.com already has mail → not offered as a quick pick
    expect(screen.queryByRole("button", { name: "example.com" })).toBeNull()
  })

  it("renders the add-mailbox form and existing rows", () => {
    render(<MailManager domains={domains} mailboxes={mailboxes} appDomains={[]} />)
    expect(screen.getByRole("button", { name: /add mailbox/i })).toBeInTheDocument()
    expect(screen.getByText("you@example.com")).toBeInTheDocument()
  })

  it("provisions a domain and shows the DNS report on success", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ domain: "shop.io", dns_zone: "shop.io", dns_records: [] }),
          { status: 200 },
        ),
      ),
    )
    render(<MailManager domains={[]} mailboxes={[]} appDomains={["shop.io"]} />)
    fireEvent.change(screen.getByLabelText("Mail domain"), { target: { value: "shop.io" } })
    fireEvent.click(screen.getByRole("button", { name: /add domain/i }))

    expect(await screen.findByText(/shop\.io is ready/i)).toBeInTheDocument()
  })

  it("surfaces an alert when a delete fails instead of throwing (regression)", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true)
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network down")))
    render(<MailManager domains={domains} mailboxes={mailboxes} appDomains={[]} />)

    fireEvent.click(screen.getByRole("button", { name: "Delete you@example.com" }))
    expect(await screen.findByRole("alert")).toBeInTheDocument()
  })
})
