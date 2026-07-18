"use client"

import type { ColumnDef } from "@tanstack/react-table"

import { DataTable } from "@/components/ui/data-table"
import { StatusBadge } from "@/components/ui/status-badge"
import type { ErrorIssue } from "@/lib/types"
import { formatRelativeLabel } from "@/lib/utils"

const columns: ColumnDef<ErrorIssue>[] = [
  {
    accessorKey: "level",
    header: "Level",
    cell: ({ row }) => <StatusBadge value={row.original.level} />,
  },
  {
    accessorKey: "title",
    header: "Issue",
    cell: ({ row }) => (
      <div>
        {row.original.permalink ? (
          <a
            href={row.original.permalink}
            target="_blank"
            rel="noreferrer"
            className="font-medium text-foreground hover:text-foreground"
          >
            {row.original.title}
          </a>
        ) : (
          <span className="font-medium text-foreground">{row.original.title}</span>
        )}
        {row.original.culprit ? (
          <div className="mt-0.5 font-mono text-xs text-muted-foreground">
            {row.original.culprit}
          </div>
        ) : null}
      </div>
    ),
  },
  {
    accessorKey: "count",
    header: "Events",
    cell: ({ row }) => (
      <div className="text-right font-mono tabular-nums text-foreground">{row.original.count}</div>
    ),
  },
  {
    accessorKey: "user_count",
    header: "Users",
    cell: ({ row }) => (
      <div className="text-right font-mono tabular-nums text-muted-foreground">
        {row.original.user_count}
      </div>
    ),
  },
  {
    accessorKey: "last_seen",
    header: "Last seen",
    cell: ({ row }) => (
      <div className="text-right font-mono text-muted-foreground">
        {row.original.last_seen ? formatRelativeLabel(row.original.last_seen) : "—"}
      </div>
    ),
  },
]

/** Unresolved GlitchTip issues for one app. */
export function ErrorIssuesTable({ issues }: { issues: ErrorIssue[] }) {
  return (
    <DataTable
      title="Unresolved issues"
      action={<span className="text-sm text-muted-foreground">{issues.length} open</span>}
      columns={columns}
      data={issues}
      getRowId={(issue) => issue.id}
      searchPlaceholder="Search issues…"
      searchLabel="Search issues"
      emptyMessage="No unresolved errors. 🎉"
    />
  )
}
