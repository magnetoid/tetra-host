"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"

import { AlertBanner } from "@/components/ui/alert-banner"
import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/ui/empty-state"
import { faKey, faPlus, faTrash } from "@/lib/icons"
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import type { AppEnvVar } from "@/lib/types"

const INPUT_CLASS =
  "rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/25"

export function EnvManager({ project, vars }: { project: string; vars: AppEnvVar[] }) {
  const router = useRouter()
  const [key, setKey] = useState("")
  const [value, setValue] = useState("")
  const [isSecret, setIsSecret] = useState(false)
  const [pending, setPending] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function call(path: string, init: RequestInit, tag: string) {
    setPending(tag)
    setError(null)
    try {
      const response = await fetch(path, init)
      const payload = (await response.json().catch(() => ({}))) as { detail?: string }
      if (!response.ok) {
        setError(payload.detail ?? "Request failed.")
        return false
      }
      router.refresh()
      return true
    } catch {
      setError("Unable to reach the control plane.")
      return false
    } finally {
      setPending(null)
    }
  }

  async function addVar(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const ok = await call(
      `/api/proxy/deploys/${project}/env`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key, value, is_secret: isSecret }),
      },
      "add",
    )
    if (ok) {
      setKey("")
      setValue("")
      setIsSecret(false)
    }
  }

  return (
    <div className="space-y-6">
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}

      <form
        onSubmit={addVar}
        className="flex flex-wrap items-end gap-3 rounded-2xl border border-border bg-muted p-4"
      >
        <label className="block text-sm">
          <span className="mb-2 block text-zinc-400">Key</span>
          <input
            aria-label="Key"
            value={key}
            onChange={(event) => setKey(event.target.value)}
            placeholder="DATABASE_URL"
            className={`${INPUT_CLASS} font-mono`}
            required
          />
        </label>
        <label className="block flex-1 text-sm">
          <span className="mb-2 block text-zinc-400">Value</span>
          <input
            aria-label="Value"
            value={value}
            onChange={(event) => setValue(event.target.value)}
            type={isSecret ? "password" : "text"}
            className={`${INPUT_CLASS} w-full font-mono`}
            required
          />
        </label>
        <label className="mb-2.5 flex items-center gap-2 text-sm text-zinc-400">
          <input
            aria-label="Secret"
            type="checkbox"
            checked={isSecret}
            onChange={(event) => setIsSecret(event.target.checked)}
            className="h-4 w-4 accent-[var(--primary)]"
          />
          Secret
        </label>
        <Button type="submit" icon={faPlus} disabled={pending !== null}>
          {pending === "add" ? "…" : "Set"}
        </Button>
      </form>

      {vars.length === 0 ? (
        <EmptyState
          title="No environment variables"
          description="Variables are injected on the next deploy. Secrets are encrypted at rest and masked here."
        />
      ) : (
        <div className="overflow-hidden rounded-2xl border border-border">
          {vars.map((row, index) => (
            <div
              key={row.key}
              className={`flex flex-wrap items-center justify-between gap-3 bg-muted px-4 py-3 ${
                index > 0 ? "border-t border-border" : ""
              }`}
            >
              <div className="flex min-w-0 items-center gap-3 font-mono text-sm">
                <span className="font-medium text-zinc-200">{row.key}</span>
                <span className="truncate text-zinc-500">{row.value}</span>
                {row.is_secret ? (
                  <span className="flex items-center gap-1 rounded-full border border-amber-900 bg-amber-950 px-2 py-0.5 text-[10px] text-amber-300">
                    <FontAwesomeIcon icon={faKey} className="h-2.5 w-2.5" />
                    secret
                  </span>
                ) : null}
              </div>
              <Button
                size="sm"
                variant="danger"
                icon={faTrash}
                disabled={pending !== null}
                onClick={() =>
                  call(`/api/proxy/deploys/${project}/env/${row.key}`, { method: "DELETE" }, `rm:${row.key}`)
                }
              >
                {pending === `rm:${row.key}` ? "…" : "Remove"}
              </Button>
            </div>
          ))}
        </div>
      )}

      <p className="text-xs text-zinc-600">
        Changes apply on the next deploy or rollback of <span className="font-mono">{project}</span>.
      </p>
    </div>
  )
}
