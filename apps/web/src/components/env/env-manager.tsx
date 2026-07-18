"use client"

import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import { useState } from "react"

import { AlertBanner } from "@/components/ui/alert-banner"
import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/ui/empty-state"
import { Input } from "@/components/ui/input"
import { useAction } from "@/hooks/use-action"
import { apiFetch } from "@/lib/client-api"
import { faKey, faPlus, faTrash } from "@/lib/icons"

/**
 * The one environment-variable manager, parameterized by deploy target —
 * replaces the two diverged copies (native-engine vs Coolify) that drifted on
 * endpoints, delete keys, and features.
 */
export type EnvTarget =
  | { kind: "deploy"; project: string } // native Tetra engine — key-addressed, supports is_secret
  | { kind: "app"; applicationId: string } // Coolify application — uuid-addressed, values masked

export type EnvRow = {
  uuid?: string
  id?: string
  key?: string
  value?: string
  is_secret?: boolean
}

function rowId(target: EnvTarget, row: EnvRow): string {
  return target.kind === "deploy" ? (row.key ?? "") : (row.uuid ?? row.id ?? "")
}

function endpoints(target: EnvTarget) {
  return target.kind === "deploy"
    ? {
        add: `/api/proxy/deploys/${target.project}/env`,
        remove: (id: string) => `/api/proxy/deploys/${target.project}/env/${id}`,
      }
    : {
        add: `/api/proxy/projects/${target.applicationId}/envs`,
        remove: (id: string) => `/api/proxy/projects/${target.applicationId}/envs/${id}`,
      }
}

export function EnvManager({ target, vars }: { target: EnvTarget; vars: EnvRow[] }) {
  const { run, pending, error } = useAction()
  const [key, setKey] = useState("")
  const [value, setValue] = useState("")
  const [isSecret, setIsSecret] = useState(false)
  const [reveal, setReveal] = useState(false)

  const api = endpoints(target)
  // Coolify returns values masked-by-default in this console; the native engine
  // masks only rows flagged is_secret.
  const masked = (row: EnvRow) => (target.kind === "app" ? !reveal : Boolean(row.is_secret))

  async function addVar(event: React.FormEvent<HTMLFormElement>) {
    const trimmedKey = key.trim()
    event.preventDefault()
    const ok = await run(
      () =>
        apiFetch(api.add, {
          method: "POST",
          body:
            target.kind === "deploy"
              ? { key: trimmedKey, value, is_secret: isSecret }
              : { key: trimmedKey, value },
          errorMessage: "Could not save variable.",
        }),
      { key: "add" },
    )
    if (ok) {
      setKey("")
      setValue("")
      setIsSecret(false)
    }
  }

  return (
    <div className="space-y-4">
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}

      <form onSubmit={addVar} className="grid gap-2 sm:grid-cols-[1fr_1.5fr_auto_auto]">
        <Input
          aria-label="Variable key"
          required
          placeholder="DATABASE_URL"
          value={key}
          onChange={(event) => setKey(event.target.value)}
          className="font-mono"
        />
        <Input
          aria-label="Variable value"
          required
          placeholder="value"
          type={isSecret ? "password" : "text"}
          value={value}
          onChange={(event) => setValue(event.target.value)}
          className="font-mono"
        />
        {target.kind === "deploy" ? (
          <label className="flex items-center gap-2 text-sm text-muted-foreground">
            <input
              type="checkbox"
              checked={isSecret}
              onChange={(event) => setIsSecret(event.target.checked)}
              className="size-4 accent-[var(--primary)]"
            />
            Secret
          </label>
        ) : null}
        <Button type="submit" variant="primary" icon={faPlus} disabled={pending !== null}>
          {pending === "add" ? "Saving…" : "Add"}
        </Button>
      </form>

      {vars.length === 0 ? (
        <EmptyState
          title="No environment variables"
          description="Variables are injected on the next deploy. Secrets are encrypted at rest and masked here."
        />
      ) : (
        <div className="divide-y divide-border overflow-hidden rounded-lg border border-border">
          {vars.map((row, index) => {
            const id = rowId(target, row)
            return (
              <div
                key={id || index}
                className="flex flex-wrap items-center justify-between gap-3 bg-background px-4 py-3"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2 font-mono text-sm">
                    <span className="font-medium text-foreground">{row.key}</span>
                    {row.is_secret ? (
                      <span className="flex items-center gap-1 rounded-full border border-status-warn/25 bg-status-warn/10 px-2 py-0.5 text-[10px] text-status-warn">
                        <FontAwesomeIcon icon={faKey} className="h-2.5 w-2.5" />
                        secret
                      </span>
                    ) : null}
                  </div>
                  <div className="truncate font-mono text-xs text-muted-foreground">
                    {masked(row) ? "••••••••" : (row.value ?? "")}
                  </div>
                </div>
                <Button
                  size="sm"
                  variant="danger"
                  icon={faTrash}
                  disabled={pending !== null || !id}
                  onClick={() =>
                    run(
                      () =>
                        apiFetch(api.remove(id), {
                          method: "DELETE",
                          errorMessage: "Could not remove variable.",
                        }),
                      { key: `rm:${id}` },
                    )
                  }
                >
                  {pending === `rm:${id}` ? "…" : "Remove"}
                </Button>
              </div>
            )
          })}
        </div>
      )}

      {target.kind === "app" && vars.length > 0 ? (
        <button
          type="button"
          onClick={() => setReveal((current) => !current)}
          className="text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          {reveal ? "Hide values" : "Reveal values"}
        </button>
      ) : null}

      <p className="text-xs text-muted-foreground">
        Changes apply on the next deploy
        {target.kind === "deploy" ? (
          <>
            {" "}
            of <span className="font-mono">{target.project}</span>
          </>
        ) : null}
        .
      </p>
    </div>
  )
}
