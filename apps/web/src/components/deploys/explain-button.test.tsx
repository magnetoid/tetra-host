import { cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ExplainButton } from "@/components/deploys/explain-button"
import type { BuildDiagnosis } from "@/lib/types"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const DIAGNOSIS: BuildDiagnosis = {
  deployment_id: "dep-1",
  status: "error",
  summary: "No Dockerfile found and Nixpacks couldn't detect a build.",
  category: "build-config",
  likely_causes: ["No Dockerfile at the repo root."],
  suggested_fixes: ["Add a Dockerfile, or a package.json start script."],
  confidence: "high",
  source: "ai",
}

describe("ExplainButton", () => {
  it("fetches and renders the diagnosis on click", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => DIAGNOSIS })
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()
    render(<ExplainButton deploymentId="dep-1" />)

    await user.click(screen.getByRole("button", { name: /explain/i }))

    expect(fetchMock).toHaveBeenCalledWith("/api/proxy/deploys/dep-1/explain")
    expect(await screen.findByText(/no dockerfile found/i)).toBeInTheDocument()
    expect(screen.getByText(/add a dockerfile/i)).toBeInTheDocument()
    expect(screen.getByText("build-config")).toBeInTheDocument()
    expect(screen.getByText(/via claude/i)).toBeInTheDocument()
  })

  it("surfaces an API error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, json: async () => ({ detail: "Deployment not found." }) }),
    )
    const user = userEvent.setup()
    render(<ExplainButton deploymentId="dep-x" />)
    await user.click(screen.getByRole("button", { name: /explain/i }))
    expect(await screen.findByText(/deployment not found/i)).toBeInTheDocument()
  })
})
