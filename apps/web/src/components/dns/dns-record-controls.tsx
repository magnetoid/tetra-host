"use client"

import { useRouter } from "next/navigation"
import { useState } from "react"

import { AlertBanner } from "@/components/ui/alert-banner"

const RECORD_TYPES = ["A", "AAAA", "CNAME", "TXT", "MX", "NS", "CAA"] as const

const inputClass =
  "rounded-lg border border-border bg-background px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-zinc-500 focus:outline-none"

export function CreateRecordForm({ zoneId }: { zoneId: string }) {
  const router = useRouter()
  const [type, setType] = useState<string>("A")
  const [name, setName] = useState("")
  const [content, setContent] = useState("")
  const [ttl, setTtl] = useState(1)
  const [proxied, setProxied] = useState(false)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setPending(true)
    setError(null)
    try {
      const response = await fetch(`/api/proxy/dns/zones/${zoneId}/records`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type, name, content, ttl, proxied }),
      })
      if (!response.ok) {
        const payload = (await response.json().catch(() => ({}))) as { detail?: string }
        setError(payload.detail ?? "Could not create record.")
        return
      }
      setName("")
      setContent("")
      router.refresh()
    } catch {
      setError("Unable to reach the control plane.")
    } finally {
      setPending(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3 rounded-2xl border border-border bg-muted p-4">
      <div className="text-sm font-medium text-zinc-300">Add DNS record</div>
      <div className="grid gap-2 sm:grid-cols-[5rem_1fr_1fr_4rem]">
        <select
          aria-label="Record type"
          value={type}
          onChange={(event) => setType(event.target.value)}
          className={inputClass}
        >
          {RECORD_TYPES.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
        <input
          aria-label="Record name"
          required
          placeholder="name (e.g. app)"
          value={name}
          onChange={(event) => setName(event.target.value)}
          className={inputClass}
        />
        <input
          aria-label="Record content"
          required
          placeholder="content (e.g. 1.2.3.4)"
          value={content}
          onChange={(event) => setContent(event.target.value)}
          className={inputClass}
        />
        <input
          aria-label="TTL"
          type="number"
          min={1}
          value={ttl}
          onChange={(event) => setTtl(Number(event.target.value) || 1)}
          className={inputClass}
        />
      </div>
      <div className="flex items-center justify-between gap-3">
        <label className="flex items-center gap-2 text-sm text-zinc-400">
          <input
            type="checkbox"
            checked={proxied}
            onChange={(event) => setProxied(event.target.checked)}
          />
          Proxied
        </label>
        <button
          type="submit"
          disabled={pending}
          className="rounded-lg bg-white px-4 py-2 text-sm font-medium text-black transition hover:bg-zinc-200 disabled:opacity-60"
        >
          {pending ? "Adding…" : "Add record"}
        </button>
      </div>
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}
    </form>
  )
}

export function DeleteRecordButton({ zoneId, recordId }: { zoneId: string; recordId: string }) {
  const router = useRouter()
  const [pending, setPending] = useState(false)

  async function remove() {
    setPending(true)
    try {
      await fetch(`/api/proxy/dns/zones/${zoneId}/records/${recordId}`, { method: "DELETE" })
      router.refresh()
    } finally {
      setPending(false)
    }
  }

  return (
    <button
      type="button"
      disabled={pending}
      onClick={remove}
      className="rounded-md border border-red-900 px-2 py-1 text-xs text-red-300 transition hover:bg-red-950 disabled:opacity-60"
    >
      {pending ? "…" : "Delete"}
    </button>
  )
}
