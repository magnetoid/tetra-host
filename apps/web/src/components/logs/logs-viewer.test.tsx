import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { LogsViewer } from "@/components/logs/logs-viewer"
import type { InstalledApp } from "@/lib/types"

afterEach(() => cleanup())

const APPS: InstalledApp[] = [
  { project: "blog", name: "Blog", template: "ghost", status: "running", domain: "blog.test" },
]

describe("LogsViewer", () => {
  it("renders the app picker, filter, and a load control", () => {
    render(<LogsViewer apps={APPS} />)
    expect(screen.getByLabelText("App")).toBeInTheDocument()
    expect(screen.getByLabelText("Filter")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /load/i })).toBeInTheDocument()
    expect(screen.getByText(/select an app and load its logs/i)).toBeInTheDocument()
  })

  it("shows an empty state with no apps", () => {
    render(<LogsViewer apps={[]} />)
    expect(screen.getByText(/no apps to show logs for/i)).toBeInTheDocument()
  })
})
