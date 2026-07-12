import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: () => {} }) }))
vi.mock("@fortawesome/react-fontawesome", () => ({ FontAwesomeIcon: () => null }))

import { MailManager } from "@/components/mail/mail-manager"

afterEach(cleanup)

const domains = [
  { domain_name: "example.com", mailboxes: 2, aliases: 1, quota_bytes: 1024, active: true },
]
const mailboxes = [
  { username: "you@example.com", name: "You", domain: "example.com", quota_bytes: 1024, messages: 0, active: true },
]

describe("MailManager", () => {
  it("offers app domains as quick picks, excluding ones that already have mail", () => {
    render(<MailManager domains={domains} mailboxes={mailboxes} appDomains={["shop.io", "example.com"]} />)
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
})
