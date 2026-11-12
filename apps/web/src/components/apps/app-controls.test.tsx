import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {}, refresh: () => {} }) }))

import { AppControls } from "@/components/apps/app-controls"
import { AppVolumes } from "@/components/apps/app-volumes"

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function stubFetch(status = 200, body: unknown = { ok: true, message: "done" }) {
  const fetchMock = vi.fn(async () =>
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  )
  vi.stubGlobal("fetch", fetchMock)
  return fetchMock
}

describe("AppControls", () => {
  it("restarts the app through the proxy", async () => {
    const fetchMock = stubFetch()
    render(<AppControls project="my blog" />)

    fireEvent.click(screen.getByRole("button", { name: "Restart" }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe("/api/proxy/apps/my%20blog/restart")
    expect(init.method).toBe("POST")
  })

  it("shows the backend's error when an action fails", async () => {
    stubFetch(403, { detail: "Provider actions are disabled (ENABLE_PROVIDER_ACTIONS=false)." })
    render(<AppControls project="blog" />)

    fireEvent.click(screen.getByRole("button", { name: "Stop" }))

    expect(await screen.findByText(/provider actions are disabled/i)).toBeInTheDocument()
  })
})

describe("AppVolumes", () => {
  it("lists mounts with volume names and container paths", () => {
    render(
      <AppVolumes
        mounts={[
          { service: "db", type: "volume", name: "blog_db", destination: "/var/lib/mysql", read_only: false },
          { service: "web", type: "bind", name: "", destination: "/etc/php.ini", read_only: true },
        ]}
      />,
    )
    expect(screen.getByText("blog_db")).toBeInTheDocument()
    expect(screen.getByText("/var/lib/mysql")).toBeInTheDocument()
    expect(screen.getByText("bind mount")).toBeInTheDocument()
    expect(screen.getByText("read-only")).toBeInTheDocument()
  })

  it("explains what having no volumes means", () => {
    render(<AppVolumes mounts={[]} />)
    expect(screen.getByText(/nothing it writes survives a redeploy/i)).toBeInTheDocument()
  })
})
