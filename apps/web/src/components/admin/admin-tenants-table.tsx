"use client"

import type { ColumnDef } from "@tanstack/react-table"

import { DataTable } from "@/components/ui/data-table"
import { StatusBadge } from "@/components/ui/status-badge"
import type { TenantRecord } from "@/lib/types"

const columns: ColumnDef<TenantRecord>[] = [
  {
    accessorKey: "name",
    header: "Name",
    cell: ({ row }) => <span className="font-medium">{row.original.name}</span>,
  },
  {
    accessorKey: "slug",
    header: "Slug",
    cell: ({ row }) => (
      <span className="font-mono text-xs text-muted-foreground">{row.original.slug}</span>
    ),
  },
  {
    accessorKey: "is_active",
    header: "Status",
    cell: ({ row }) => <StatusBadge value={row.original.is_active ? "Active" : "Inactive"} />,
  },
]

/** The tenant summary panel on the Admin page. */
export function AdminTenantsTable({ tenants }: { tenants: TenantRecord[] }) {
  return (
    <DataTable
      title="Tenants"
      action={
        <span className="text-sm text-muted-foreground">
          {tenants.length} record{tenants.length === 1 ? "" : "s"}
        </span>
      }
      columns={columns}
      data={tenants}
      getRowId={(tenant) => tenant.id}
      emptyMessage="No tenants yet."
    />
  )
}
