"use client"

import type { ReactNode } from "react"
import type { ColumnDef } from "@tanstack/react-table"

import { DataTable } from "@/components/ui/data-table"
import { StatusBadge } from "@/components/ui/status-badge"
import type { AuditEventRecord } from "@/lib/types"

function formatWhen(iso: string): string {
  if (!iso) return ""
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString()
}

const baseColumns: ColumnDef<AuditEventRecord>[] = [
  {
    accessorKey: "created_at",
    header: "When",
    cell: ({ row }) => (
      <span className="whitespace-nowrap font-mono text-xs tabular-nums text-muted-foreground">
        {formatWhen(row.original.created_at)}
      </span>
    ),
  },
  {
    accessorKey: "action",
    header: "Action",
    cell: ({ row }) => <StatusBadge value={row.original.action} />,
  },
  {
    accessorKey: "actor_email",
    header: "Actor",
    cell: ({ row }) => (
      <span className="font-mono text-xs text-muted-foreground">{row.original.actor_email}</span>
    ),
  },
  {
    accessorKey: "target",
    header: "Target",
    cell: ({ row }) => (
      <span className="font-mono text-xs text-muted-foreground">{row.original.target}</span>
    ),
  },
]

const columnsWithDetails: ColumnDef<AuditEventRecord>[] = [
  ...baseColumns,
  {
    accessorKey: "details",
    header: "Details",
    cell: ({ row }) => (
      <div className="max-w-xs truncate text-xs text-muted-foreground">{row.original.details}</div>
    ),
  },
]

/** Audit-event listing shared by the Audit log page and the Super Admin activity feed. */
export function AuditEventsTable({
  events,
  title,
  action,
  emptyMessage,
  showDetails = false,
}: {
  events: AuditEventRecord[]
  title: string
  action?: ReactNode
  emptyMessage: string
  showDetails?: boolean
}) {
  return (
    <DataTable
      title={title}
      action={action}
      columns={showDetails ? columnsWithDetails : baseColumns}
      data={events}
      emptyMessage={emptyMessage}
    />
  )
}
