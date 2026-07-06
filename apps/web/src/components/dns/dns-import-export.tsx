"use client"

import { useRouter } from "next/navigation"
import { useRef, useState } from "react"

import { AlertBanner } from "@/components/ui/alert-banner"

const buttonClass =
  "rounded-lg border border-border px-3 py-1.5 text-sm text-foreground transition-colors hover:bg-accent disabled:opacity-60"

/** Bulk BIND import (upload) + export (download) for a zone's DNS records. */
export function DnsImportExport({ zoneId, zoneName }: { zoneId: string; zoneName: string }) {
  const router = useRouter()
  const fileInput = useRef<HTMLInputElement>(null)
  const [pending, setPending] = useState<"export" | "import" | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function exportZone() {
    setPending("export")
    setMessage(null)
    setError(null)
    try {
      const response = await fetch(`/api/proxy/dns/zones/${zoneId}/export`)
      const payload = (await response.json().catch(() => ({}))) as {
        bind?: string
        record_count?: number
        detail?: string
      }
      if (!response.ok || typeof payload.bind !== "string") {
        setError(payload.detail ?? "Export failed.")
        return
      }
      downloadText(`${zoneName || zoneId}.txt`, payload.bind)
      setMessage(`Exported ${payload.record_count ?? 0} records.`)
    } catch {
      setError("Unable to reach the control plane.")
    } finally {
      setPending(null)
    }
  }

  async function importZone(file: File) {
    setPending("import")
    setMessage(null)
    setError(null)
    try {
      const bind = await file.text()
      const response = await fetch(`/api/proxy/dns/zones/${zoneId}/import`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bind }),
      })
      const payload = (await response.json().catch(() => ({}))) as { message?: string; detail?: string }
      if (!response.ok) {
        setError(payload.detail ?? "Import failed.")
        return
      }
      setMessage(payload.message ?? "Records imported.")
      router.refresh()
    } catch {
      setError("Unable to read or upload the zone file.")
    } finally {
      setPending(null)
      if (fileInput.current) {
        fileInput.current.value = ""
      }
    }
  }

  return (
    <div className="space-y-4 rounded-2xl border border-border bg-muted p-6">
      <div>
        <h2 className="text-lg font-semibold">Bulk records</h2>
        <p className="mt-1 text-sm text-muted-foreground">Import or export this zone as a BIND zone file.</p>
      </div>
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={exportZone} disabled={pending !== null} className={buttonClass}>
          {pending === "export" ? "Exporting…" : "Export BIND"}
        </button>
        <button
          type="button"
          onClick={() => fileInput.current?.click()}
          disabled={pending !== null}
          className={buttonClass}
        >
          {pending === "import" ? "Importing…" : "Import BIND"}
        </button>
        <input
          ref={fileInput}
          type="file"
          accept=".txt,.bind,.zone,text/plain"
          className="hidden"
          aria-label="BIND zone file"
          onChange={(event) => {
            const file = event.target.files?.[0]
            if (file) {
              void importZone(file)
            }
          }}
        />
      </div>
      {message ? <AlertBanner tone="success">{message}</AlertBanner> : null}
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}
    </div>
  )
}

function downloadText(filename: string, content: string) {
  const blob = new Blob([content], { type: "text/plain" })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}
