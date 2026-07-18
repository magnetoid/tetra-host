"use client"

import type { ColumnDef } from "@tanstack/react-table"

import { TenantRowActions } from "@/components/tenants/tenant-row-actions"
import { DataTable } from "@/components/ui/data-table"
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
    accessorKey: "plan_key",
    header: "Plan",
    cell: ({ row }) => (
      <span className="font-mono text-xs text-muted-foreground">{row.original.plan_key || "—"}</span>
    ),
  },
  {
    id: "actions",
    enableSorting: false,
    header: () => <span className="block text-right">Actions</span>,
    cell: ({ row }) => <TenantRowActions tenant={row.original} />,
  },
]

/** The Super Admin approval queue: tenants in the pending state. */
export function PendingTenantsTable({ tenants }: { tenants: TenantRecord[] }) {
  return (
    <DataTable
      title="Pending approval"
      action={<span className="text-sm text-muted-foreground">{tenants.length} waiting</span>}
      columns={columns}
      data={tenants}
      getRowId={(tenant) => tenant.id}
      emptyMessage="No tenants awaiting approval. New signups in the pending state appear here for review."
    />
  )
}
