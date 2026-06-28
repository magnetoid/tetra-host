"use client"

import { useMemo, useState } from "react"

import { DeleteRecordButton, RecordForm } from "@/components/dns/dns-record-controls"
import type { DNSRecord } from "@/lib/types"

export function DnsRecordsTable({ zoneId, records }: { zoneId: string; records: DNSRecord[] }) {
  const [query, setQuery] = useState("")
  const [editingId, setEditingId] = useState<string | null>(null)

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) {
      return records
    }
    return records.filter((r) => `${r.type} ${r.name} ${r.content}`.toLowerCase().includes(q))
  }, [query, records])

  return (
    <div className="rounded-2xl border border-border bg-muted p-6">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">DNS records</h2>
        <input
          aria-label="Search records"
          placeholder="Search type / name / content…"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          className="w-56 rounded-lg border border-border bg-background px-3 py-1.5 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-zinc-500 focus:outline-none"
        />
      </div>
      <div className="mt-4 overflow-hidden rounded-2xl border border-border">
        <table className="min-w-full divide-y divide-border text-sm">
          <thead className="bg-background/60 text-left text-zinc-500">
            <tr>
              <th className="px-4 py-3 font-medium">Type</th>
              <th className="px-4 py-3 font-medium">Name</th>
              <th className="px-4 py-3 font-medium">Content</th>
              <th className="px-4 py-3 font-medium">TTL</th>
              <th className="px-4 py-3 font-medium">Proxy</th>
              <th className="px-4 py-3 text-right font-medium">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border bg-background">
            {filtered.length > 0 ? (
              filtered.map((record) =>
                editingId === record.id ? (
                  <tr key={record.id}>
                    <td colSpan={6} className="p-3">
                      <RecordForm zoneId={zoneId} record={record} onDone={() => setEditingId(null)} />
                    </td>
                  </tr>
                ) : (
                  <tr key={record.id}>
                    <td className="px-4 py-3">{record.type}</td>
                    <td className="px-4 py-3 text-zinc-300">{record.name}</td>
                    <td className="px-4 py-3 text-zinc-400">{record.content}</td>
                    <td className="px-4 py-3 text-zinc-400">{record.ttl === 1 ? "Auto" : record.ttl}</td>
                    <td className="px-4 py-3">
                      {record.proxied ? (
                        <span className="text-amber-400">● Proxied</span>
                      ) : (
                        <span className="text-zinc-500">DNS only</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          type="button"
                          onClick={() => setEditingId(record.id)}
                          className="rounded-md border border-border px-2 py-1 text-xs text-zinc-300 transition hover:bg-zinc-900"
                        >
                          Edit
                        </button>
                        <DeleteRecordButton zoneId={zoneId} recordId={record.id} />
                      </div>
                    </td>
                  </tr>
                ),
              )
            ) : (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-zinc-500">
                  {records.length > 0 ? "No records match your search." : "Select a zone to browse records."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
