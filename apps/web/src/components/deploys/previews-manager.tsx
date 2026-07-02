"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"

import { AlertBanner } from "@/components/ui/alert-banner"
import { Button } from "@/components/ui/button"
import { faTrash } from "@/lib/icons"
import type { PreviewRecord } from "@/lib/types"

export function PreviewsManager({ previews }: { previews: PreviewRecord[] }) {
  const router = useRouter()
  const [pending, setPending] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function removePreview(previewId: string) {
    setPending(previewId)
    setError(null)
    try {
      const response = await fetch(`/api/proxy/previews/${previewId}`, { method: "DELETE" })
      if (!response.ok) {
        const payload = (await response.json().catch(() => ({}))) as { detail?: string }
        setError(payload.detail ?? "Could not tear down the preview.")
        return
      }
      router.refresh()
    } catch {
      setError("Unable to reach the control plane.")
    } finally {
      setPending(null)
    }
  }

  return (
    <div className="space-y-4">
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}

      {previews.length === 0 ? (
        <p className="text-sm text-zinc-500">
          No preview environments — push any branch of a hooked repository and it gets its own
          URL. Deleting the branch tears the preview down.
        </p>
      ) : (
        <div className="space-y-2">
          {previews.map((preview) => (
            <div
              key={preview.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-border bg-muted px-4 py-3"
            >
              <div className="flex min-w-0 items-center gap-3 text-sm">
                <span className="font-medium">{preview.project}</span>
                <span className="font-mono text-xs text-zinc-500">@{preview.branch}</span>
                {preview.domain ? (
                  <a
                    href={`https://${preview.domain}`}
                    target="_blank"
                    rel="noreferrer"
                    className="truncate font-mono text-xs text-cyan-400 hover:underline"
                  >
                    {preview.domain}
                  </a>
                ) : null}
              </div>
              <Button
                size="sm"
                variant="danger"
                icon={faTrash}
                disabled={pending !== null}
                onClick={() => removePreview(preview.id)}
              >
                {pending === preview.id ? "…" : "Tear down"}
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
