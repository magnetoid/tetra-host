"use client"

import { useState } from "react"
import type { ColumnDef } from "@tanstack/react-table"

import { DeleteRecordButton, RecordForm } from "@/components/dns/dns-record-controls"
import { DataTable } from "@/components/ui/data-table"
import type { DNSRecord } from "@/lib/types"

export function DnsRecordsTable({ zoneId, records }: { zoneId: string; records: DNSRecord[] }) {
  const [editingId, setEditingId] = useState<string | null>(null)

  const columns: ColumnDef<DNSRecord>[] = [
    {
      accessorKey: "type",
      header: "Type",
      cell: ({ row }) => <span className="font-mono">{row.original.type}</span>,
    },
    {
      accessorKey: "name",
      header: "Name",
      cell: ({ row }) => <span className="font-mono text-foreground">{row.original.name}</span>,
    },
    {
      accessorKey: "content",
      header: "Content",
      cell: ({ row }) => (
        <span className="font-mono text-muted-foreground">{row.original.content}</span>
      ),
    },
    {
      accessorKey: "ttl",
      header: "TTL",
      cell: ({ row }) => (
        <span className="font-mono tabular-nums text-muted-foreground">
          {row.original.ttl === 1 ? "Auto" : row.original.ttl}
        </span>
      ),
    },
    {
      accessorKey: "proxied",
      header: "Proxy",
      cell: ({ row }) =>
        row.original.proxied ? (
          <span className="text-status-live">● Proxied</span>
        ) : (
          <span className="text-muted-foreground">DNS only</span>
        ),
    },
    {
      id: "actions",
      enableSorting: false,
      header: () => <span className="block text-right">Actions</span>,
      cell: ({ row }) => (
        <div className="flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={() => setEditingId(row.original.id)}
            className="rounded-md border border-border px-2 py-1 text-xs text-foreground transition-colors hover:bg-accent"
          >
            Edit
          </button>
          <DeleteRecordButton zoneId={zoneId} recordId={row.original.id} />
        </div>
      ),
    },
  ]

  return (
    <DataTable
      title="DNS records"
      columns={columns}
      data={records}
      getRowId={(record) => record.id}
      searchPlaceholder="Search type / name / content…"
      searchLabel="Search records"
      emptyMessage={
        records.length > 0 ? "No records match your search." : "Select a zone to browse records."
      }
      editingRowId={editingId}
      renderEditRow={(record) => (
        <RecordForm zoneId={zoneId} record={record} onDone={() => setEditingId(null)} />
      )}
    />
  )
}
