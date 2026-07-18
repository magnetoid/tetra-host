"use client"

import { useCallback, useEffect, useState } from "react"

import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"

import { Button } from "@/components/ui/button"
import { AlertBanner } from "@/components/ui/alert-banner"
import { useAction } from "@/hooks/use-action"
import { apiFetch } from "@/lib/client-api"
import { faArrowsRotate, faCircleCheck, faTrash } from "@/lib/icons"
import type { MailQuarantineItem } from "@/lib/types"

/**
 * Spam quarantine: held/rejected mail scoped to the tenant's recipients. Release
 * delivers to the inbox (and learns as ham); delete drops the held copy. Data is
 * fetched client-side so it stays fresh without reloading the whole mail page.
 */
export function QuarantinePanel() {
  const { run, pending } = useAction()
  const [items, setItems] = useState<MailQuarantineItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Pure fetch (no setState) so the mount effect drives it through promise
  // callbacks — keeps setState out of the synchronous effect body.
  const fetchList = useCallback(
    () =>
      apiFetch<MailQuarantineItem[]>("/api/proxy/mail/quarantine", {
        errorMessage: "Could not load quarantine.",
      }),
    [],
  )

  useEffect(() => {
    let cancelled = false
    fetchList()
      .then((data) => {
        if (!cancelled) {
          setItems(data)
          setError(null)
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Could not load quarantine.")
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [fetchList])

  // Manual refresh / post-action reload — runs from event handlers.
  const reload = useCallback(async () => {
    setLoading(true)
    try {
      setItems(await fetchList())
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load quarantine.")
    } finally {
      setLoading(false)
    }
  }, [fetchList])

  async function release(id: number) {
    await run(
      async () => {
        await apiFetch("/api/proxy/mail/quarantine/actions", {
          method: "POST",
          body: { ids: [id], action: "release" },
          errorMessage: "Could not release message.",
        })
        await reload()
      },
      { key: `rel-${id}`, refresh: false, successMessage: "Message released" },
    )
  }

  async function remove(id: number) {
    await run(
      async () => {
        await apiFetch("/api/proxy/mail/quarantine/delete", {
          method: "POST",
          body: { ids: [id] },
          errorMessage: "Could not delete message.",
        })
        await reload()
      },
      { key: `del-${id}`, refresh: false, successMessage: "Message deleted" },
    )
  }

  return (
    <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Spam quarantine</h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Held or rejected mail for your recipients. Release trusted mail to the inbox, or delete
            it.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            void reload()
          }}
          disabled={loading}
          className="inline-flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-2 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground disabled:opacity-50"
        >
          <FontAwesomeIcon icon={faArrowsRotate} className="h-3.5 w-3.5" />
          Refresh
        </button>
      </div>

      {error ? (
        <div className="mt-4">
          <AlertBanner tone="error">{error}</AlertBanner>
        </div>
      ) : null}

      <div className="mt-4 space-y-2">
        {loading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : items.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nothing in quarantine — inbox is clean.</p>
        ) : (
          items.map((item) => (
            <div
              key={item.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-background p-4"
            >
              <div className="min-w-0">
                <div className="truncate text-sm font-medium">{item.subject || "(no subject)"}</div>
                <div className="mt-0.5 truncate font-mono text-xs text-muted-foreground">
                  {item.sender || "unknown"} → {item.rcpt}
                  {item.score ? ` · score ${item.score.toFixed(1)}` : ""}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  icon={faCircleCheck}
                  disabled={pending !== null}
                  onClick={() => release(item.id)}
                >
                  {pending === `rel-${item.id}` ? "Releasing…" : "Release"}
                </Button>
                <button
                  type="button"
                  onClick={() => remove(item.id)}
                  disabled={pending !== null}
                  className="rounded-lg border border-border p-2 text-muted-foreground transition-colors hover:border-status-err/40 hover:text-status-err disabled:opacity-50"
                  aria-label={`Delete quarantined message ${item.subject}`}
                >
                  <FontAwesomeIcon icon={faTrash} className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </section>
  )
}
