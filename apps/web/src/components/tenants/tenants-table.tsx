"use client"

import type { ColumnDef } from "@tanstack/react-table"

import { TenantRowActions } from "@/components/tenants/tenant-row-actions"
import { DataTable } from "@/components/ui/data-table"
import type { TenantRecord } from "@/lib/types"

const STATUS_COLORS: Record<string, string> = {
  active: "text-status-ok",
  pending: "text-status-warn",
  suspended: "text-status-warn",
  rejected: "text-status-err",
}

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
    id: "status",
    accessorFn: (tenant) => tenant.status ?? "active",
    header: "Status",
    cell: ({ row }) => {
      const status = row.original.status ?? "active"
      return (
        <span
          className={`text-xs font-medium capitalize ${
            STATUS_COLORS[status] ?? "text-muted-foreground"
          }`}
        >
          {status}
        </span>
      )
    },
  },
  {
    accessorKey: "plan_key",
    header: "Plan",
    cell: ({ row }) => (
      <span className="font-mono text-xs text-muted-foreground">{row.original.plan_key ?? "—"}</span>
    ),
  },
  {
    id: "actions",
    enableSorting: false,
    header: () => <span className="block text-right">Actions</span>,
    cell: ({ row }) => <TenantRowActions tenant={row.original} />,
  },
]

export function TenantsTable({ tenants }: { tenants: TenantRecord[] }) {
  return (
    <DataTable
      title="All tenants"
      action={
        <span className="text-sm text-muted-foreground">
          {tenants.length} tenant{tenants.length === 1 ? "" : "s"}
        </span>
      }
      columns={columns}
      data={tenants}
      getRowId={(tenant) => tenant.id}
      searchPlaceholder="Search name / slug…"
      searchLabel="Search tenants"
      emptyMessage="No tenants yet."
    />
  )
}
