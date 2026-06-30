import { afterEach, describe, expect, it, vi } from "vitest"
import { act, cleanup, render, screen } from "@testing-library/react"

import { LogStream } from "@/components/projects/log-stream"

type Listener = (event: MessageEvent) => void

class MockEventSource {
  static instances: MockEventSource[] = []
  url: string
  closed = false
  private listeners: Record<string, Listener[]> = {}

  constructor(url: string) {
    this.url = url
    MockEventSource.instances.push(this)
  }

  addEventListener(type: string, listener: Listener) {
    const bucket = this.listeners[type] ?? []
    bucket.push(listener)
    this.listeners[type] = bucket
  }

  close() {
    this.closed = true
  }

  emit(type: string, data: unknown) {
    const event = { data: JSON.stringify(data) } as MessageEvent
    for (const listener of this.listeners[type] ?? []) {
      listener(event)
    }
  }
}

afterEach(() => {
  cleanup()
  MockEventSource.instances = []
  vi.unstubAllGlobals()
})

describe("LogStream", () => {
  it("connects to the stream endpoint and renders streamed lines + status", () => {
    vi.stubGlobal("EventSource", MockEventSource)

    render(<LogStream applicationId="app-1" deploymentId="dep-1" />)

    const source = MockEventSource.instances[0]
    expect(source.url).toContain("/api/stream/projects/app-1/deployments/dep-1/logs/stream")

    act(() => {
      source.emit("status", { status: "in_progress" })
      source.emit("log", { output: "Building image", type: "stdout", timestamp: "" })
      source.emit("log", { output: "boom", type: "stderr", timestamp: "" })
    })

    expect(screen.getByText("Building image")).toBeInTheDocument()
    expect(screen.getByText("boom")).toBeInTheDocument()
    expect(screen.getByText("in_progress")).toBeInTheDocument()
  })

  it("shows the final status and closes the stream on done", () => {
    vi.stubGlobal("EventSource", MockEventSource)

    render(<LogStream applicationId="app-1" deploymentId="dep-9" />)
    const source = MockEventSource.instances[0]

    act(() => {
      source.emit("status", { status: "in_progress" })
      source.emit("done", { status: "finished" })
    })

    expect(screen.getByText("finished")).toBeInTheDocument()
    expect(source.closed).toBe(true)
  })
})
