import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: () => {}, push: () => {} }) }))

import { DatabaseBackups, hasRunningOperation } from "@/components/databases/database-backups"
import { DatabaseControls } from "@/components/databases/database-controls"
import { DatabasesManager, describeSchedule } from "@/components/databases/databases-manager"
import type { DatabaseBackupRecord, DatabaseEngine, DatabaseRecord } from "@/lib/types"

afterEach(() => cleanup())

const ENGINES: DatabaseEngine[] = [
  { key: "postgres", label: "PostgreSQL", versions: ["17", "16"], default_version: "17", supports_backup: true },
  { key: "redis", label: "Redis", versions: ["7"], default_version: "7", supports_backup: false },
]

const DB: DatabaseRecord = {
  id: "db-1", name: "blog-db", engine: "postgres", engine_label: "PostgreSQL", version: "17",
  status: "running(1)", host: "blog-db", port: 5432, supports_backup: true,
  backup_cron: "0 3 * * *", backup_keep: 7, created_at: "2026-11-13T03:00:00Z",
}

const BACKUP: DatabaseBackupRecord = {
  id: "bk-1", status: "ok", trigger: "scheduled", size_bytes: 4096, error: "",
  restore_status: "", restore_error: "", restored_at: null,
  created_at: "2026-11-13T03:00:00Z", finished_at: "2026-11-13T03:00:04Z",
}

describe("describeSchedule", () => {
  it("names the default and the off state", () => {
    expect(describeSchedule("0 3 * * *")).toBe("Daily backups, 03:00 UTC")
    expect(describeSchedule("")).toBe("Backups off")
    expect(describeSchedule("0 */6 * * *")).toBe("Backups: 0 */6 * * * (UTC)")
  })
})

describe("DatabasesManager", () => {
  it("shows the empty state and the engine versions", () => {
    render(<DatabasesManager databases={[]} engines={ENGINES} />)
    expect(screen.getByText(/no databases yet/i)).toBeInTheDocument()
    expect(screen.getByLabelText("Version")).toHaveValue("17")
    fireEvent.change(screen.getByLabelText("Engine"), { target: { value: "redis" } })
    expect(screen.getByText(/backups are not\s+offered/i)).toBeInTheDocument()
  })

  it("lists databases with a link to their page", () => {
    render(<DatabasesManager databases={[DB]} engines={ENGINES} />)
    expect(screen.getByRole("link", { name: "blog-db" })).toHaveAttribute("href", "/databases/db-1")
    expect(screen.getByText("blog-db:5432")).toBeInTheDocument()
  })
})

describe("DatabaseBackups", () => {
  it("offers restore only for finished backups", () => {
    render(<DatabaseBackups database={DB} backups={[BACKUP, { ...BACKUP, id: "bk-2", status: "error", error: "boom" }]} />)
    const restores = screen.getAllByRole("button", { name: /restore/i })
    expect(restores[0]).toBeEnabled()
    expect(restores[1]).toBeDisabled()
    expect(screen.getByText("boom")).toBeInTheDocument()
  })

  it("detects running operations", () => {
    expect(hasRunningOperation([BACKUP])).toBe(false)
    expect(hasRunningOperation([{ ...BACKUP, restore_status: "running" }])).toBe(true)
  })

  it("explains that redis has no backups", () => {
    render(<DatabaseBackups database={{ ...DB, engine: "redis", engine_label: "Redis", supports_backup: false }} backups={[]} />)
    expect(screen.getByText(/aren.t offered/i)).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /back up now/i })).not.toBeInTheDocument()
  })
})

describe("DatabaseControls", () => {
  it("keeps delete disabled until the name is typed", () => {
    render(<DatabaseControls database={DB} />)
    fireEvent.click(screen.getByRole("button", { name: /delete/i }))
    const confirm = screen.getByRole("button", { name: /delete database/i })
    expect(confirm).toBeDisabled()
    fireEvent.change(screen.getByLabelText("Database name"), { target: { value: "blog-db" } })
    expect(confirm).toBeEnabled()
  })
})
