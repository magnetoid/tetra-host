import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

const refresh = vi.fn()
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }) }))

import { DeleteRecordButton, RecordForm } from "@/components/dns/dns-record-controls"
import type { DNSRecord } from "@/lib/types"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  refresh.mockClear()
})

function okFetch() {
  const mock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }))
  vi.stubGlobal("fetch", mock)
  return mock
}

function bodyOf(mock: ReturnType<typeof vi.fn>) {
  return JSON.parse((mock.mock.calls[0][1] as RequestInit).body as string)
}

describe("RecordForm (create)", () => {
  it("POSTs a new record, then clears inputs and calls onDone", async () => {
    const fetchMock = okFetch()
    const onDone = vi.fn()
    render(<RecordForm zoneId="z1" onDone={onDone} />)

    fireEvent.change(screen.getByLabelText("Record name"), { target: { value: "app" } })
    fireEvent.change(screen.getByLabelText("Record content"), { target: { value: "1.2.3.4" } })
    fireEvent.click(screen.getByRole("button", { name: "Add record" }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe("/api/proxy/dns/zones/z1/records")
    expect((init as RequestInit).method).toBe("POST")
    expect(bodyOf(fetchMock)).toMatchObject({ type: "A", name: "app", content: "1.2.3.4" })

    await waitFor(() => expect(onDone).toHaveBeenCalled())
    expect((screen.getByLabelText("Record name") as HTMLInputElement).value).toBe("")
  })

  it("reveals a priority field for MX and includes priority in the body", async () => {
    const fetchMock = okFetch()
    render(<RecordForm zoneId="z1" />)

    expect(screen.queryByLabelText("Priority")).toBeNull()
    fireEvent.change(screen.getByLabelText("Record type"), { target: { value: "MX" } })
    expect(screen.getByLabelText("Priority")).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText("Record name"), { target: { value: "@" } })
    fireEvent.change(screen.getByLabelText("Record content"), {
      target: { value: "mail.example.com" },
    })
    fireEvent.click(screen.getByRole("button", { name: "Add record" }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    expect(bodyOf(fetchMock)).toMatchObject({ type: "MX", priority: 10 })
  })

  it("surfaces the backend error and does not clear inputs", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "Invalid content." }), { status: 400 }),
      ),
    )
    render(<RecordForm zoneId="z1" />)
    fireEvent.change(screen.getByLabelText("Record name"), { target: { value: "app" } })
    fireEvent.change(screen.getByLabelText("Record content"), { target: { value: "bad" } })
    fireEvent.click(screen.getByRole("button", { name: "Add record" }))

    const alert = await screen.findByRole("alert")
    expect(alert.textContent).toContain("Invalid content.")
    expect((screen.getByLabelText("Record name") as HTMLInputElement).value).toBe("app")
  })
})

describe("RecordForm (edit)", () => {
  it("PUTs to the record's URL", async () => {
    const fetchMock = okFetch()
    const record: DNSRecord = {
      id: "r1",
      type: "A",
      name: "app",
      content: "1.1.1.1",
      ttl: 1,
      proxied: false,
    }
    render(<RecordForm zoneId="z1" record={record} />)

    fireEvent.click(screen.getByRole("button", { name: "Save changes" }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe("/api/proxy/dns/zones/z1/records/r1")
    expect((init as RequestInit).method).toBe("PUT")
  })
})

describe("DeleteRecordButton", () => {
  it("DELETEs the record", async () => {
    const fetchMock = okFetch()
    render(<DeleteRecordButton zoneId="z1" recordId="r1" />)

    fireEvent.click(screen.getByRole("button", { name: "Delete" }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe("/api/proxy/dns/zones/z1/records/r1")
    expect((init as RequestInit).method).toBe("DELETE")
  })
})
