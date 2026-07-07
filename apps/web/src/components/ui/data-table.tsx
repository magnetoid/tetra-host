"use client"

import { useState, type ReactNode } from "react"
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import {
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  type SortingState,
  useReactTable,
} from "@tanstack/react-table"

import { faChevronDown } from "@/lib/icons"
import { cn } from "@/lib/utils"

type DataTableProps<TData> = {
  columns: ColumnDef<TData, unknown>[]
  data: TData[]
  title?: string
  action?: ReactNode
  searchPlaceholder?: string
  searchLabel?: string
  emptyMessage?: string
  getRowId?: (row: TData) => string
  /** When a row's id matches, render this in place of the cells (spans all columns). */
  editingRowId?: string | null
  renderEditRow?: (row: TData) => ReactNode
}

/** Reusable dense data table (TanStack v8): sortable headers, global search, sticky
 *  header, tabular numerals, token-styled. Optional inline-edit-row slot. */
export function DataTable<TData>({
  columns,
  data,
  title,
  action,
  searchPlaceholder,
  searchLabel,
  emptyMessage = "No results.",
  getRowId,
  editingRowId,
  renderEditRow,
}: DataTableProps<TData>) {
  const [sorting, setSorting] = useState<SortingState>([])
  const [globalFilter, setGlobalFilter] = useState("")

  const table = useReactTable({
    data,
    columns,
    state: { sorting, globalFilter },
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    getRowId: getRowId ? (row) => getRowId(row) : undefined,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
  })

  const rows = table.getRowModel().rows

  return (
    <div className="rounded-2xl border border-border bg-muted p-6">
      {(title || action || searchPlaceholder) && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          {title ? <h2 className="font-display text-lg font-semibold">{title}</h2> : <span />}
          <div className="flex items-center gap-2">
            {action}
            {searchPlaceholder ? (
              <input
                aria-label={searchLabel ?? searchPlaceholder}
                placeholder={searchPlaceholder}
                value={globalFilter}
                onChange={(event) => setGlobalFilter(event.target.value)}
                className="w-56 rounded-lg border border-border bg-background px-3 py-1.5 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none"
              />
            ) : null}
          </div>
        </div>
      )}

      <div className="mt-4 overflow-hidden rounded-2xl border border-border">
        <div className="max-h-[34rem] overflow-auto">
          <table className="min-w-full divide-y divide-border text-sm">
            <thead className="sticky top-0 z-10 bg-background text-left text-muted-foreground">
              {table.getHeaderGroups().map((headerGroup) => (
                <tr key={headerGroup.id}>
                  {headerGroup.headers.map((header) => {
                    const sortable = header.column.getCanSort()
                    const sorted = header.column.getIsSorted()
                    return (
                      <th key={header.id} className="whitespace-nowrap px-4 py-3 font-medium">
                        {header.isPlaceholder ? null : sortable ? (
                          <button
                            type="button"
                            onClick={header.column.getToggleSortingHandler()}
                            className="flex items-center gap-1.5 transition-colors hover:text-foreground"
                          >
                            {flexRender(header.column.columnDef.header, header.getContext())}
                            <FontAwesomeIcon
                              icon={faChevronDown}
                              className={cn(
                                "h-2.5 w-2.5 transition-transform",
                                sorted === "asc" && "rotate-180 text-foreground",
                                sorted === "desc" && "text-foreground",
                                !sorted && "opacity-30",
                              )}
                            />
                          </button>
                        ) : (
                          flexRender(header.column.columnDef.header, header.getContext())
                        )}
                      </th>
                    )
                  })}
                </tr>
              ))}
            </thead>
            <tbody className="divide-y divide-border bg-background">
              {rows.length > 0 ? (
                rows.map((row) => {
                  if (editingRowId && renderEditRow && row.id === editingRowId) {
                    return (
                      <tr key={row.id}>
                        <td colSpan={columns.length} className="p-3">
                          {renderEditRow(row.original)}
                        </td>
                      </tr>
                    )
                  }
                  return (
                    <tr key={row.id} className="transition-colors hover:bg-muted/40">
                      {row.getVisibleCells().map((cell) => (
                        <td key={cell.id} className="px-4 py-3">
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </td>
                      ))}
                    </tr>
                  )
                })
              ) : (
                <tr>
                  <td colSpan={columns.length} className="px-4 py-6 text-muted-foreground">
                    {emptyMessage}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
