"use client"

import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import { useState } from "react"

import { AlertBanner } from "@/components/ui/alert-banner"
import { Button } from "@/components/ui/button"
import { useAction } from "@/hooks/use-action"
import { apiFetch } from "@/lib/client-api"
import { faKey, faPlus, faTrash } from "@/lib/icons"
import type { ApiTokenCreated, ApiTokenSummary } from "@/lib/types"

const INPUT_CLASS =
  "rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/25"

/**
 * Self-service personal API tokens (parity with `tetra tokens …`). The plaintext
 * secret is revealed exactly once, right after creation. Mirrors the deploy-hooks
 * manager: `useAction` + `apiFetch`, list re-rendered by router.refresh().
 */
export function ApiTokensManager({ tokens }: { tokens: ApiTokenSummary[] }) {
  const { run, pending, error } = useAction()
  const [name, setName] = useState("")
  const [readOnly, setReadOnly] = useState(false)
  const [created, setCreated] = useState<ApiTokenCreated | null>(null)

  async function createToken(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    await run(
      async () => {
        const payload = await apiFetch<ApiTokenCreated>("/api/proxy/account/tokens", {
          method: "POST",
          body: { name, read_only: readOnly },
          errorMessage: "Could not create token.",
        })
        setCreated(payload)
        setName("")
        setReadOnly(false)
      },
      { key: "create" },
    )
  }

  function revokeToken(tokenId: string) {
    return run(
      async () => {
        await apiFetch(`/api/proxy/account/tokens/${tokenId}`, {
          method: "DELETE",
          errorMessage: "Could not revoke token.",
        })
        if (created?.id === tokenId) setCreated(null)
      },
      { key: `rm:${tokenId}`, successMessage: "Token revoked" },
    )
  }

  return (
    <div className="space-y-4">
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}

      <form
        onSubmit={createToken}
        className="flex flex-wrap items-end gap-3 rounded-lg border border-border bg-muted p-4"
      >
        <label className="block flex-1 text-sm">
          <span className="mb-2 block text-muted-foreground">Token name</span>
          <input
            aria-label="Token name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="ci, laptop, deploy-bot…"
            className={`${INPUT_CLASS} w-full`}
            required
          />
        </label>
        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          <input
            type="checkbox"
            aria-label="Read-only token"
            checked={readOnly}
            onChange={(event) => setReadOnly(event.target.checked)}
            className="h-4 w-4 rounded border-border"
          />
          Read-only
        </label>
        <Button type="submit" icon={faPlus} disabled={pending !== null}>
          {pending === "create" ? "…" : "Create token"}
        </Button>
      </form>

      {created ? (
        <div className="rounded-lg border border-status-ok/25 bg-status-ok/10 p-4 text-sm">
          <div className="font-medium text-status-ok">
            Token created — copy it now. It is shown only once.
          </div>
          <div className="mt-3 break-all rounded-md border border-border bg-background p-3 font-mono text-xs text-foreground">
            {created.token}
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            Use it as a Bearer token:{" "}
            <span className="font-mono">Authorization: Bearer {created.prefix}…</span>, or with the
            CLI (<span className="font-mono">TETRA_TOKEN</span>).
          </p>
        </div>
      ) : null}

      {tokens.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No API tokens yet — create one to use the <span className="font-mono">tetra</span> CLI or
          call the API from CI without a login session.
        </p>
      ) : (
        <div className="space-y-2">
          {tokens.map((token) => (
            <div
              key={token.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-muted px-4 py-3"
            >
              <div className="flex min-w-0 items-center gap-3 text-sm">
                <FontAwesomeIcon icon={faKey} className="h-3.5 w-3.5 text-muted-foreground" />
                <span className="font-medium">{token.name}</span>
                {token.scope === "read" ? (
                  <span className="rounded-full border border-status-warn/40 bg-status-warn/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-status-warn">
                    read-only
                  </span>
                ) : null}
                <span className="font-mono text-xs text-muted-foreground">{token.prefix}…</span>
                <span className="text-xs text-muted-foreground">
                  {token.last_used_at ? "in use" : "never used"}
                </span>
              </div>
              <Button
                size="sm"
                variant="danger"
                icon={faTrash}
                disabled={pending !== null}
                onClick={() => revokeToken(token.id)}
              >
                {pending === `rm:${token.id}` ? "…" : "Revoke"}
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
