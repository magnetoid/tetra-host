"use client"

import { useRouter } from "next/navigation"
import { useState } from "react"

import { AlertBanner } from "@/components/ui/alert-banner"

export type EnvVar = {
  uuid?: string
  id?: string
  key?: string
  value?: string
}

function envId(env: EnvVar): string {
  return env.uuid ?? env.id ?? ""
}

const inputClass =
  "rounded-lg border border-border bg-background px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-zinc-500 focus:outline-none"

export function EnvManager({
  applicationId,
  initialEnvs,
}: {
  applicationId: string
  initialEnvs: EnvVar[]
}) {
  const router = useRouter()
  const [key, setKey] = useState("")
  const [value, setValue] = useState("")
  const [reveal, setReveal] = useState(false)
  const [pending, setPending] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function add(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setPending("add")
    setError(null)
    try {
      const response = await fetch(`/api/proxy/projects/${applicationId}/envs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key, value }),
      })
      if (!response.ok) {
        const payload = (await response.json().catch(() => ({}))) as { detail?: string }
        setError(payload.detail ?? "Could not save variable.")
        return
      }
      setKey("")
      setValue("")
      router.refresh()
    } catch {
      setError("Unable to reach the control plane.")
    } finally {
      setPending(null)
    }
  }

  async function remove(id: string) {
    if (!id) {
      return
    }
    setPending(id)
    try {
      await fetch(`/api/proxy/projects/${applicationId}/envs/${id}`, { method: "DELETE" })
      router.refresh()
    } finally {
      setPending(null)
    }
  }

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Environment variables</h2>
        {initialEnvs.length > 0 ? (
          <button
            type="button"
            onClick={() => setReveal((current) => !current)}
            className="text-sm text-zinc-400 hover:text-zinc-200"
          >
            {reveal ? "Hide values" : "Reveal values"}
          </button>
        ) : null}
      </div>

      <form onSubmit={add} className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
        <input
          aria-label="Variable key"
          required
          placeholder="KEY"
          value={key}
          onChange={(event) => setKey(event.target.value)}
          className={inputClass}
        />
        <input
          aria-label="Variable value"
          required
          placeholder="value"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          className={inputClass}
        />
        <button
          type="submit"
          disabled={pending !== null}
          className="rounded-lg bg-white px-4 py-2 text-sm font-medium text-black transition hover:bg-zinc-200 disabled:opacity-60"
        >
          {pending === "add" ? "Saving…" : "Add"}
        </button>
      </form>

      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}

      <div className="divide-y divide-border overflow-hidden rounded-2xl border border-border">
        {initialEnvs.length === 0 ? (
          <div className="p-4 text-sm text-zinc-500">No environment variables yet.</div>
        ) : (
          initialEnvs.map((env, index) => {
            const id = envId(env)
            return (
              <div key={id || index} className="flex items-center justify-between gap-3 bg-background p-3">
                <div className="min-w-0">
                  <div className="font-mono text-sm text-zinc-200">{env.key}</div>
                  <div className="truncate font-mono text-xs text-zinc-500">
                    {reveal ? env.value ?? "" : "••••••••"}
                  </div>
                </div>
                <button
                  type="button"
                  disabled={pending !== null || !id}
                  onClick={() => remove(id)}
                  className="shrink-0 rounded-md border border-red-900 px-2 py-1 text-xs text-red-300 transition hover:bg-red-950 disabled:opacity-60"
                >
                  {pending === id ? "…" : "Delete"}
                </button>
              </div>
            )
          })
        )}
      </div>
    </section>
  )
}
