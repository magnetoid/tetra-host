"use client"

import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import { useState } from "react"

import { AlertBanner } from "@/components/ui/alert-banner"
import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/ui/empty-state"
import { Input } from "@/components/ui/input"
import { useAction } from "@/hooks/use-action"
import { apiFetch } from "@/lib/client-api"
import { faKey, faLink, faPlus, faTrash } from "@/lib/icons"
import type { ServiceReferenceTarget } from "@/lib/types"

/**
 * Environment variables of one engine app (`/deploys/{project}/env`). Rows are
 * key-addressed; values flagged `is_secret` are encrypted at rest and masked.
 *
 * A value can reference a service in the app's environment as `${{service.field}}`
 * (`references` lists them); the deploy fills in its current details.
 */
export type EnvRow = {
  key?: string
  value?: string
  is_secret?: boolean
  references?: string[]
}

export const referenceToken = (service: string, field: string) => `\${{${service}.${field}}}`

const REFERENCE = /\$\{\{\s*[a-z][a-z0-9-]*\.[a-z_]+\s*\}\}/

/** A conventional variable name for a reference, used when the key is still empty. */
function suggestedKey(target: ServiceReferenceTarget, field: string): string {
  if (field !== "url") return ""
  return target.engine === "redis" ? "REDIS_URL" : "DATABASE_URL"
}

export function EnvManager({
  project,
  vars,
  references,
}: {
  project: string
  vars: EnvRow[]
  /** Services this app can reference; omit to hide the picker. */
  references?: ServiceReferenceTarget[]
}) {
  const { run, pending, error } = useAction()
  const [key, setKey] = useState("")
  const [value, setValue] = useState("")
  const [isSecret, setIsSecret] = useState(false)

  const base = `/api/proxy/deploys/${encodeURIComponent(project)}/env`
  const hasReference = REFERENCE.test(value)

  function insertReference(choice: string) {
    const [service, field] = choice.split("|")
    const target = references?.find((t) => t.service === service)
    if (!target || !field) return
    setValue((current) => current + referenceToken(service, field))
    if (!key.trim()) setKey(suggestedKey(target, field))
  }

  async function addVar(event: React.FormEvent<HTMLFormElement>) {
    const trimmedKey = key.trim()
    event.preventDefault()
    const ok = await run(
      () =>
        apiFetch(base, {
          method: "POST",
          body: { key: trimmedKey, value, is_secret: isSecret },
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
          type={isSecret && !hasReference ? "password" : "text"}
          value={value}
          onChange={(event) => setValue(event.target.value)}
          className="font-mono"
        />
        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          <input
            type="checkbox"
            checked={isSecret}
            onChange={(event) => setIsSecret(event.target.checked)}
            className="size-4 accent-[var(--primary)]"
          />
          Secret
        </label>
        <Button type="submit" variant="primary" icon={faPlus} disabled={pending !== null}>
          {pending === "add" ? "Saving…" : "Add"}
        </Button>
      </form>

      {references ? (
        references.length > 0 ? (
          <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
            <FontAwesomeIcon icon={faLink} className="size-3" />
            <label htmlFor="env-reference">Reference a service</label>
            <select
              id="env-reference"
              value=""
              onChange={(event) => insertReference(event.target.value)}
              className="rounded-md border border-border bg-background px-2 py-1 font-mono text-xs text-foreground"
            >
              <option value="">Choose…</option>
              {references.map((target) => (
                <optgroup key={target.service} label={`${target.service} (${target.engine})`}>
                  {target.fields.map((field) => (
                    <option key={field} value={`${target.service}|${field}`}>
                      {referenceToken(target.service, field)}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
            <span className="text-xs">Filled in with the current value on every deploy.</span>
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">
            To reference a database here, create it in this app&apos;s environment.
          </p>
        )
      ) : null}

      {vars.length === 0 ? (
        <EmptyState
          title="No environment variables"
          description="Variables are injected on the next deploy. Secrets are encrypted at rest and masked here."
        />
      ) : (
        <div className="divide-y divide-border overflow-hidden rounded-lg border border-border">
          {vars.map((row, index) => {
            const id = row.key ?? ""
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
                    {(row.references ?? []).map((ref) => (
                      <span
                        key={ref}
                        title="Filled in from this service on every deploy"
                        className="flex items-center gap-1 rounded-full border border-primary/25 bg-primary/10 px-2 py-0.5 text-[10px] text-primary"
                      >
                        <FontAwesomeIcon icon={faLink} className="h-2.5 w-2.5" />
                        {ref}
                      </span>
                    ))}
                  </div>
                  <div className="truncate font-mono text-xs text-muted-foreground">
                    {row.is_secret ? "••••••••" : (row.value ?? "")}
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
                        apiFetch(`${base}/${encodeURIComponent(id)}`, {
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

      <p className="text-xs text-muted-foreground">
        Changes apply on the next deploy of <span className="font-mono">{project}</span>.
      </p>
    </div>
  )
}
