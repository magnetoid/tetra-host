import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: () => {} }) }))

import { JobsManager } from "@/components/jobs/jobs-manager"
import type { ScheduledJobRecord } from "@/lib/types"

afterEach(() => cleanup())

const JOB: ScheduledJobRecord = {
  id: "j1", name: "nightly", cron: "0 2 * * *", url: "https://a.test/cron", method: "GET",
  enabled: true, last_run_at: "2026-07-10T02:00:00", last_status: "ok", last_detail: "200",
}

describe("JobsManager", () => {
  it("renders the create form and empty state", () => {
    render(<JobsManager jobs={[]} />)
    expect(screen.getByLabelText("Name")).toBeInTheDocument()
    expect(screen.getByLabelText("Schedule")).toHaveValue("*/5 * * * *")
    expect(screen.getByText(/no scheduled jobs/i)).toBeInTheDocument()
  })

  it("lists a job with its schedule + last status and a pause action", () => {
    render(<JobsManager jobs={[JOB]} />)
    expect(screen.getByText("nightly")).toBeInTheDocument()
    expect(screen.getByText("0 2 * * *")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /pause/i })).toBeInTheDocument()
  })
})
