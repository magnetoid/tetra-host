"use client"

import { useMemo, useState } from "react"
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"

import { AlertBanner } from "@/components/ui/alert-banner"
import { Button } from "@/components/ui/button"
import { Modal } from "@/components/ui/modal"
import { useAction } from "@/hooks/use-action"
import { apiFetch } from "@/lib/client-api"
import { faCircleCheck, faKey, faPlus, faTrash } from "@/lib/icons"
import type { AiKey, AiKeyCreated, AiModel } from "@/lib/types"

const FIELD =
  "w-full rounded-lg border border-border bg-background px-3 py-1.5 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none"

export function AiReseller({ models, keys }: { models: AiModel[]; keys: AiKey[] }) {
  const { run, pending, error } = useAction()
  const [query, setQuery] = useState("")
  const [label, setLabel] = useState("")
  const [limit, setLimit] = useState("")
  const [created, setCreated] = useState<AiKeyCreated | null>(null)

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase()
    const list = q ? models.filter((m) => `${m.id} ${m.name}`.toLowerCase().includes(q)) : models
    return list.slice(0, 40)
  }, [models, query])

  async function provision(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    await run(
      async () => {
        const payload = await apiFetch<AiKeyCreated>("/api/proxy/ai/keys", {
          method: "POST",
          body: { label, limit: limit ? Number(limit) : null, limit_reset: "monthly" },
          errorMessage: "Could not provision the key.",
        })
        setCreated(payload)
        setLabel("")
        setLimit("")
      },
      { key: "provision" },
    )
  }

  function keyAction(hash: string, method: "DELETE" | "PATCH", body?: object, done?: string) {
    return run(
      () =>
        apiFetch(`/api/proxy/ai/keys/${hash}`, {
          method,
          body,
          errorMessage: "Key action failed.",
        }),
      { key: `${method}:${hash}`, successMessage: done },
    )
  }

  return (
    <div className="space-y-6">
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}

      {/* Provision */}
      <form onSubmit={provision} className="rounded-lg border border-border bg-muted/40 p-5">
        <h3 className="text-base font-medium">Provision an AI key</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          Mint a per-tenant OpenRouter key with a monthly spend cap. The secret is shown once.
        </p>
        <div className="mt-4 flex flex-wrap items-end gap-3">
          <label className="flex-1">
            <span className="text-xs font-medium text-muted-foreground">Label</span>
            <input
              aria-label="Key label"
              required
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="acme-production"
              className={`${FIELD} mt-1`}
            />
          </label>
          <label>
            <span className="text-xs font-medium text-muted-foreground">Spend cap (USD/mo)</span>
            <input
              aria-label="Spend cap"
              type="number"
              min={0}
              step="1"
              value={limit}
              onChange={(e) => setLimit(e.target.value)}
              placeholder="optional"
              className={`${FIELD} mt-1 w-40`}
            />
          </label>
          <Button type="submit" variant="primary" icon={faKey} disabled={pending !== null}>
            Provision
          </Button>
        </div>
      </form>

      {/* Provisioned keys */}
      <div>
        <h3 className="mb-3 text-base font-medium">Provisioned keys</h3>
        {keys.length === 0 ? (
          <p className="text-sm text-muted-foreground">No AI keys yet — provision one above.</p>
        ) : (
          <div className="space-y-2">
            {keys.map((k) => (
              <div
                key={k.hash}
                className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-muted/40 p-3"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{k.label || k.name || "key"}</span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs ${k.disabled ? "bg-status-err/10 text-status-err" : "bg-status-ok/10 text-status-ok"}`}
                    >
                      {k.disabled ? "disabled" : "active"}
                    </span>
                  </div>
                  <div className="mt-0.5 font-mono text-xs text-muted-foreground">
                    {k.hash} · usage ${k.usage ?? 0}
                    {k.limit != null ? ` / $${k.limit}` : " / ∞"}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={pending !== null}
                    onClick={() =>
                      keyAction(
                        k.hash,
                        "PATCH",
                        { disabled: !k.disabled },
                        k.disabled ? "Key enabled" : "Key disabled",
                      )
                    }
                  >
                    {k.disabled ? "Enable" : "Disable"}
                  </Button>
                  <Button
                    size="sm"
                    variant="danger"
                    icon={faTrash}
                    disabled={pending !== null}
                    onClick={() => keyAction(k.hash, "DELETE", undefined, "Key revoked")}
                  >
                    Revoke
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Model catalog */}
      <div>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <h3 className="text-base font-medium">Model catalog</h3>
          <input
            aria-label="Search models"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search models…"
            className={`${FIELD} w-64`}
          />
        </div>
        {models.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No models — set OPENROUTER_PROVISIONING_KEY to enable AI reselling.
          </p>
        ) : (
          <div className="max-h-80 space-y-1 overflow-y-auto rounded-xl border border-border bg-muted/40 p-2">
            {shown.map((m) => (
              <div key={m.id} className="flex items-center justify-between gap-3 rounded-lg px-2 py-1.5 text-sm">
                <div className="min-w-0">
                  <span className="font-medium">{m.name || m.id}</span>
                  <span className="ml-2 font-mono text-xs text-muted-foreground">{m.id}</span>
                </div>
                <span className="shrink-0 font-mono text-xs text-muted-foreground">
                  ctx {m.context_length.toLocaleString()}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Secret-once modal */}
      <Modal
        open={created !== null}
        onOpenChange={(open) => {
          if (!open) setCreated(null)
        }}
        title="AI key provisioned"
        description="Copy this key now — it will not be shown again."
      >
        {created ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm text-status-ok">
              <FontAwesomeIcon icon={faCircleCheck} className="h-4 w-4" />
              <span>
                {created.label} · cap {created.limit != null ? `$${created.limit}/mo` : "unlimited"}
              </span>
            </div>
            <code className="block break-all rounded-lg border border-border bg-black/60 p-3 font-mono text-xs text-zinc-200">
              {created.key}
            </code>
            <Button
              variant="secondary"
              icon={faPlus}
              onClick={() => navigator.clipboard?.writeText(created.key)}
            >
              Copy key
            </Button>
          </div>
        ) : null}
      </Modal>
    </div>
  )
}
