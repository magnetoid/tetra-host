import { cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {}, refresh: () => {} }) }))

import { PreviewsManager } from "@/components/deploys/previews-manager"
import type { PreviewRecord } from "@/lib/types"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const PREVIEW: PreviewRecord = {
  id: "pv1",
  project: "blog",
  branch: "feat/login",
  preview_project: "blog-git-feat-login",
  domain: "blog-git-feat-login.apps.test",
  last_deployment_id: "dep-1",
}

describe("PreviewsManager", () => {
  it("shows an empty state", () => {
    render(<PreviewsManager previews={[]} />)
    expect(screen.getByText(/no preview environments/i)).toBeInTheDocument()
  })

  it("lists previews with their branch and URL", () => {
    render(<PreviewsManager previews={[PREVIEW]} />)
    expect(screen.getByText("blog")).toBeInTheDocument()
    expect(screen.getByText("@feat/login")).toBeInTheDocument()
    const link = screen.getByRole("link", { name: "blog-git-feat-login.apps.test" })
    expect(link).toHaveAttribute("href", "https://blog-git-feat-login.apps.test")
  })

  it("tears a preview down via the API", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true }) })
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()
    render(<PreviewsManager previews={[PREVIEW]} />)
    await user.click(screen.getByRole("button", { name: /tear down/i }))
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/proxy/previews/pv1",
      expect.objectContaining({ method: "DELETE" }),
    )
  })

  it("surfaces API errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        json: async () => ({ detail: "Provider actions are disabled." }),
      }),
    )
    const user = userEvent.setup()
    render(<PreviewsManager previews={[PREVIEW]} />)
    await user.click(screen.getByRole("button", { name: /tear down/i }))
    expect(await screen.findByText(/provider actions are disabled/i)).toBeInTheDocument()
  })
})
