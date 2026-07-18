"use client"

import { useState, type ReactNode } from "react"
import type { ColumnDef } from "@tanstack/react-table"

import { PlanForm } from "@/components/plans/plan-form"
import { Button } from "@/components/ui/button"
import { DataTable } from "@/components/ui/data-table"
import { faSliders } from "@/lib/icons"
import type { Plan } from "@/lib/types"

function formatPrice(cents: number, currency: string) {
  if (cents === 0) return "Free"
  const dollars = cents / 100
  return `${currency.toUpperCase()} $${dollars.toFixed(2)}`
}

function ResourceBadge({ label, value }: { label: string; value: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-md bg-accent px-2 py-0.5 font-mono text-xs tabular-nums text-foreground">
      <span className="text-muted-foreground">{label}</span>
      {value}
    </span>
  )
}

/** Archived plans render dimmed, cell by cell (rows are styled per-cell in the DataTable). */
function dim(plan: Plan, content: ReactNode): ReactNode {
  return plan.is_archived ? <div className="opacity-50">{content}</div> : content
}

export function PlansTable({ plans }: { plans: Plan[] }) {
  const [editingId, setEditingId] = useState<string | null>(null)

  const columns: ColumnDef<Plan>[] = [
    {
      accessorKey: "key",
      header: "Key",
      cell: ({ row }) =>
        dim(
          row.original,
          <span className="font-mono text-xs text-muted-foreground">{row.original.key}</span>,
        ),
    },
    {
      accessorKey: "name",
      header: "Name",
      cell: ({ row }) =>
        dim(
          row.original,
          <div>
            <div className="font-medium">{row.original.name}</div>
            {row.original.description ? (
              <div className="text-xs text-muted-foreground">{row.original.description}</div>
            ) : null}
          </div>,
        ),
    },
    {
      accessorKey: "price_cents",
      header: "Price",
      cell: ({ row }) =>
        dim(
          row.original,
          <span className="font-mono tabular-nums text-foreground">
            {formatPrice(row.original.price_cents, row.original.currency)}
          </span>,
        ),
    },
    {
      id: "limits",
      accessorFn: (plan) => plan.max_apps,
      header: "Apps / Domains",
      cell: ({ row }) =>
        dim(
          row.original,
          <span className="font-mono tabular-nums text-muted-foreground">
            {row.original.max_apps} / {row.original.max_domains}
          </span>,
        ),
    },
    {
      id: "resources",
      enableSorting: false,
      header: "Resources",
      cell: ({ row }) =>
        dim(
          row.original,
          <div className="flex flex-wrap gap-1">
            <ResourceBadge label="CPU" value={`${row.original.cpu_millicores}m`} />
            <ResourceBadge label="Mem" value={`${row.original.mem_mb}MB`} />
            <ResourceBadge label="Disk" value={`${row.original.disk_mb}MB`} />
          </div>,
        ),
    },
    {
      accessorKey: "is_archived",
      header: "Status",
      cell: ({ row }) =>
        dim(
          row.original,
          <span
            className={
              row.original.is_archived
                ? "text-xs text-muted-foreground"
                : "text-xs font-medium text-status-ok"
            }
          >
            {row.original.is_archived ? "Archived" : "Active"}
          </span>,
        ),
    },
    {
      id: "actions",
      enableSorting: false,
      header: () => <span className="block text-right">Actions</span>,
      cell: ({ row }) =>
        dim(
          row.original,
          <div className="flex justify-end">
            <Button
              size="sm"
              variant="secondary"
              icon={faSliders}
              onClick={() => setEditingId(row.original.id)}
            >
              Edit
            </Button>
          </div>,
        ),
    },
  ]

  if (plans.length === 0) {
    return <p className="text-sm text-muted-foreground">No plans yet. Create one above.</p>
  }

  return (
    <DataTable
      columns={columns}
      data={plans}
      getRowId={(plan) => plan.id}
      searchPlaceholder="Search plans…"
      searchLabel="Search plans"
      emptyMessage="No plans match your search."
      editingRowId={editingId}
      renderEditRow={(plan) => (
        <div className="p-1">
          <div className="mb-2 text-sm font-medium text-foreground">Editing: {plan.name}</div>
          <PlanForm plan={plan} onDone={() => setEditingId(null)} />
        </div>
      )}
    />
  )
}
