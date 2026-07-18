"use client"

import { useState } from "react"

import { AlertBanner } from "@/components/ui/alert-banner"
import { useAction } from "@/hooks/use-action"
import { apiFetch } from "@/lib/client-api"
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
  const { run, pending, error } = useAction()
  const editing = Boolean(record)
  const [type, setType] = useState<string>(record?.type ?? "A")
  const [name, setName] = useState(record?.name ?? "")
  const [content, setContent] = useState(record?.content ?? "")
  const [ttl, setTtl] = useState(record?.ttl ?? 1)
  const [proxied, setProxied] = useState(Boolean(record?.proxied))
  const [priority, setPriority] = useState(record?.priority ?? 10)

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const body: Record<string, unknown> = { type, name, content, ttl, proxied }
    if (NEEDS_PRIORITY.has(type)) {
      body.priority = priority
    }
    const url = editing
      ? `/api/proxy/dns/zones/${zoneId}/records/${record!.id}`
      : `/api/proxy/dns/zones/${zoneId}/records`
    const ok = await run(
      () =>
        apiFetch(url, {
          method: editing ? "PUT" : "POST",
          body,
          errorMessage: "Could not save record.",
        }),
      { key: "save", successMessage: editing ? "DNS record updated" : "DNS record added" },
    )
    if (ok) {
      if (!editing) {
        setName("")
        setContent("")
      }
      onDone?.()
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3 rounded-lg border border-border bg-muted p-4">
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
            disabled={pending !== null}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 disabled:opacity-60"
          >
            {pending !== null ? "Saving…" : editing ? "Save changes" : "Add record"}
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
  const { run, pending } = useAction()

  return (
    <button
      type="button"
      disabled={pending !== null}
      onClick={() =>
        run(
          () =>
            apiFetch(`/api/proxy/dns/zones/${zoneId}/records/${recordId}`, {
              method: "DELETE",
              errorMessage: "Could not delete record.",
            }),
          { key: "delete", successMessage: "DNS record deleted" },
        )
      }
      className="rounded-md border border-status-err/25 px-2 py-1 text-xs text-status-err transition-colors hover:bg-status-err/10 disabled:opacity-60"
    >
      {pending !== null ? "…" : "Delete"}
    </button>
  )
}
