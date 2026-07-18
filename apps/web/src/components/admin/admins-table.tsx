"use client"

import type { ColumnDef } from "@tanstack/react-table"

import { DataTable } from "@/components/ui/data-table"
import { StatusBadge } from "@/components/ui/status-badge"
import type { AdminRecord } from "@/lib/types"

const columns: ColumnDef<AdminRecord>[] = [
  {
    accessorKey: "full_name",
    header: "Name",
    cell: ({ row }) => row.original.full_name,
  },
  {
    accessorKey: "email",
    header: "Email",
    cell: ({ row }) => (
      <span className="font-mono text-xs text-muted-foreground">{row.original.email}</span>
    ),
  },
  {
    id: "tenant",
    accessorFn: (admin) => admin.tenant_name ?? admin.tenant_slug ?? "",
    header: "Tenant",
    cell: ({ row }) => (
      <span className="text-muted-foreground">
        {row.original.tenant_name ?? row.original.tenant_slug}
      </span>
    ),
  },
  {
    accessorKey: "is_active",
    header: "Status",
    cell: ({ row }) => <StatusBadge value={row.original.is_active ? "Active" : "Inactive"} />,
  },
]

export function AdminsTable({ admins }: { admins: AdminRecord[] }) {
  return (
    <DataTable
      title="Administrators"
      action={
        <span className="text-sm text-muted-foreground">
          {admins.length} record{admins.length === 1 ? "" : "s"}
        </span>
      }
      columns={columns}
      data={admins}
      getRowId={(admin) => admin.id}
      searchPlaceholder="Search name / email…"
      searchLabel="Search administrators"
      emptyMessage="No administrators yet."
    />
  )
}
