import { cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ErrorExplainButton } from "@/components/projects/error-explain-button"
import type { ErrorDiagnosis } from "@/lib/types"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const DIAGNOSIS: ErrorDiagnosis = {
  issue_id: "42",
  title: "TypeError: profile.map is not a function",
  culprit: "app/user.tsx",
  summary: "A value was used as the wrong type.",
  category: "type-error",
  likely_causes: ["profile was not an array."],
  suggested_fixes: ["Validate the API payload before mapping."],
  confidence: "medium",
  source: "ai",
}

describe("ErrorExplainButton", () => {
  it("fetches and renders the diagnosis in a modal on click", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => DIAGNOSIS })
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()
    render(<ErrorExplainButton app="app-7" issueId="42" title="TypeError" />)

    await user.click(screen.getByRole("button", { name: /explain/i }))

    expect(fetchMock).toHaveBeenCalledWith("/api/proxy/projects/app-7/errors/42/explain")
    expect(await screen.findByText(/value was used as the wrong type/i)).toBeInTheDocument()
    expect(screen.getByText(/validate the api payload/i)).toBeInTheDocument()
    expect(screen.getByText("type-error")).toBeInTheDocument()
    expect(screen.getByText(/via claude/i)).toBeInTheDocument()
  })

  it("surfaces an API error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, json: async () => ({ detail: "Error not found." }) }),
    )
    const user = userEvent.setup()
    render(<ErrorExplainButton app="app-7" issueId="99" title="Boom" />)
    await user.click(screen.getByRole("button", { name: /explain/i }))
    expect(await screen.findByText(/error not found/i)).toBeInTheDocument()
  })
})
