"use client"

import { useRouter } from "next/navigation"
import { useState } from "react"

import { AlertBanner } from "@/components/ui/alert-banner"
import type { DNSRecord } from "@/lib/types"

const RECORD_TYPES = ["A", "AAAA", "CNAME", "TXT", "MX", "SRV", "NS", "CAA"] as const
const NEEDS_PRIORITY = new Set(["MX", "SRV"])

const inputClass =
  "rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none"

/** Create (no `record`) or edit (with `record`) a DNS record. */
export function RecordForm({
  zoneId,
  record,
  onDone,
}: {
  zoneId: string
  record?: DNSRecord
  onDone?: () => void
}) {
  const router = useRouter()
  const editing = Boolean(record)
  const [type, setType] = useState<string>(record?.type ?? "A")
  const [name, setName] = useState(record?.name ?? "")
  const [content, setContent] = useState(record?.content ?? "")
  const [ttl, setTtl] = useState(record?.ttl ?? 1)
  const [proxied, setProxied] = useState(Boolean(record?.proxied))
  const [priority, setPriority] = useState(record?.priority ?? 10)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setPending(true)
    setError(null)
    const body: Record<string, unknown> = { type, name, content, ttl, proxied }
    if (NEEDS_PRIORITY.has(type)) {
      body.priority = priority
    }
    const url = editing
      ? `/api/proxy/dns/zones/${zoneId}/records/${record!.id}`
      : `/api/proxy/dns/zones/${zoneId}/records`
    try {
      const response = await fetch(url, {
        method: editing ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })
      if (!response.ok) {
        const payload = (await response.json().catch(() => ({}))) as { detail?: string }
        setError(payload.detail ?? "Could not save record.")
        return
      }
      if (!editing) {
        setName("")
        setContent("")
      }
      router.refresh()
      onDone?.()
    } catch {
      setError("Unable to reach the control plane.")
    } finally {
      setPending(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3 rounded-2xl border border-border bg-muted p-4">
      <div className="text-sm font-medium text-foreground">{editing ? "Edit DNS record" : "Add DNS record"}</div>
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
      {NEEDS_PRIORITY.has(type) ? (
        <input
          aria-label="Priority"
          type="number"
          min={0}
          placeholder="priority (e.g. 10)"
          value={priority}
          onChange={(event) => setPriority(Number(event.target.value) || 0)}
          className={`${inputClass} sm:w-44`}
        />
      ) : null}
      <div className="flex items-center justify-between gap-3">
        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          <input type="checkbox" checked={proxied} onChange={(event) => setProxied(event.target.checked)} />
          Proxied
        </label>
        <div className="flex gap-2">
          {editing && onDone ? (
            <button
              type="button"
              onClick={onDone}
              className="rounded-lg border border-border px-3 py-2 text-sm text-foreground transition-colors hover:bg-accent"
            >
              Cancel
            </button>
          ) : null}
          <button
            type="submit"
            disabled={pending}
            className="rounded-lg bg-foreground px-4 py-2 text-sm font-medium text-background transition-colors hover:bg-foreground/90 disabled:opacity-60"
          >
            {pending ? "Saving…" : editing ? "Save changes" : "Add record"}
          </button>
        </div>
      </div>
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}
    </form>
  )
}

export function CreateRecordForm({ zoneId }: { zoneId: string }) {
  return <RecordForm zoneId={zoneId} />
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
      className="rounded-md border border-status-err/25 px-2 py-1 text-xs text-status-err transition-colors hover:bg-status-err/10 disabled:opacity-60"
    >
      {pending ? "…" : "Delete"}
    </button>
  )
}
