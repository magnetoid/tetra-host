import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: () => {} }) }))

import { DatabasesManager } from "@/components/databases/databases-manager"
import type { DatabaseRecord, DatabaseTargets } from "@/lib/types"

afterEach(() => cleanup())

const TARGETS: DatabaseTargets = {
  servers: [{ uuid: "srv-1", name: "hetzner-1" }],
  projects: [{ uuid: "proj-1", name: "default" }],
}

const DB: DatabaseRecord = {
  id: "db-1", name: "app-db", type: "postgresql", status: "running",
  internal_db_url: "postgres://user:pass@app-db:5432/app", image: "postgres:16",
}

describe("DatabasesManager", () => {
  it("renders the provision form with engine + server/project pickers", () => {
    render(<DatabasesManager databases={[]} targets={TARGETS} />)
    expect(screen.getByLabelText("Engine")).toBeInTheDocument()
    expect(screen.getByLabelText("Name")).toBeInTheDocument()
    expect(screen.getByRole("option", { name: "hetzner-1" })).toBeInTheDocument()
    expect(screen.getByRole("option", { name: "default" })).toBeInTheDocument()
    expect(screen.getByText(/no databases yet/i)).toBeInTheDocument()
  })

  it("lists a provisioned database with its engine + status", () => {
    render(<DatabasesManager databases={[DB]} targets={TARGETS} />)
    expect(screen.getByText("app-db")).toBeInTheDocument()
    // "postgresql" appears both as an engine <option> and the db's type badge.
    expect(screen.getAllByText("postgresql").length).toBeGreaterThanOrEqual(2)
  })
})
