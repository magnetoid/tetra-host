"use client"

import { AlertBanner } from "@/components/ui/alert-banner"
import { Button } from "@/components/ui/button"
import { useAction } from "@/hooks/use-action"
import { apiFetch } from "@/lib/client-api"
import { faTrash } from "@/lib/icons"
import type { PreviewRecord } from "@/lib/types"

export function PreviewsManager({ previews }: { previews: PreviewRecord[] }) {
  const { run, pending, error } = useAction()

  function removePreview(previewId: string) {
    return run(
      () =>
        apiFetch(`/api/proxy/previews/${previewId}`, {
          method: "DELETE",
          errorMessage: "Could not tear down the preview.",
        }),
      { key: previewId, successMessage: "Preview torn down" },
    )
  }

  return (
    <div className="space-y-4">
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}

      {previews.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No preview environments — push any branch of a hooked repository and it gets its own
          URL. Deleting the branch tears the preview down.
        </p>
      ) : (
        <div className="space-y-2">
          {previews.map((preview) => (
            <div
              key={preview.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-muted px-4 py-3"
            >
              <div className="flex min-w-0 items-center gap-3 text-sm">
                <span className="font-medium">{preview.project}</span>
                <span className="font-mono text-xs text-muted-foreground">@{preview.branch}</span>
                {preview.domain ? (
                  <a
                    href={`https://${preview.domain}`}
                    target="_blank"
                    rel="noreferrer"
                    className="truncate font-mono text-xs text-status-live hover:underline"
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
