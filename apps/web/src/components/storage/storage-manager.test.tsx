import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: () => {} }) }))

import { StorageManager } from "@/components/storage/storage-manager"
import type { BucketRecord, StorageStatus } from "@/lib/types"

afterEach(() => cleanup())

const ON: StorageStatus = { configured: true, can_issue_credentials: true, endpoint: "https://x.r2" }
const BUCKET: BucketRecord = { name: "st-assets", display_name: "assets", endpoint: "https://x.r2" }

describe("StorageManager", () => {
  it("shows a not-configured state when R2 is off", () => {
    render(
      <StorageManager
        buckets={[]}
        status={{ configured: false, can_issue_credentials: false, endpoint: "" }}
      />,
    )
    expect(screen.getByText(/object storage isn't configured/i)).toBeInTheDocument()
  })

  it("renders the create form and existing buckets when configured", () => {
    render(<StorageManager buckets={[BUCKET]} status={ON} />)
    expect(screen.getByLabelText("New bucket")).toBeInTheDocument()
    expect(screen.getByText("st-assets")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /create bucket/i })).toBeInTheDocument()
  })
})
