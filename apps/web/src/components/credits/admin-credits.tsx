"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import type { ColumnDef } from "@tanstack/react-table"

import { AlertBanner } from "@/components/ui/alert-banner"
import { Button } from "@/components/ui/button"
import { DataTable } from "@/components/ui/data-table"
import { EmptyState } from "@/components/ui/empty-state"
import type { TenantCreditOverview } from "@/lib/types"

const INPUT =
  "w-24 rounded-lg border border-border bg-background px-2 py-1.5 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/25"

function usd(v: number): string {
  const abs = Math.abs(v)
  return `$${v.toFixed(abs > 0 && abs < 1 ? 4 : 2)}`
}

export function AdminCredits({ rows }: { rows: TenantCreditOverview[] }) {
  const router = useRouter()
  const [amounts, setAmounts] = useState<Record<string, string>>({})
  const [pending, setPending] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  async function topup(tenantId: string) {
    const amount = Number(amounts[tenantId])
    if (!amount || amount <= 0) {
      setError("Enter a positive amount.")
      return
    }
    setPending(tenantId)
    setError(null)
    setNotice(null)
    try {
      const res = await fetch("/api/proxy/billing/credits", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tenant_id: tenantId, amount_usd: amount }),
      })
      const payload = (await res.json().catch(() => ({}))) as { detail?: string; balance_usd?: number }
      if (!res.ok) {
        setError(payload.detail ?? "Top-up failed.")
        return
      }
      setNotice(`Topped up ${usd(amount)} — new balance ${usd(payload.balance_usd ?? 0)}.`)
      setAmounts((a) => ({ ...a, [tenantId]: "" }))
      router.refresh()
    } catch {
      setError("Unable to reach the control plane.")
    } finally {
      setPending(null)
    }
  }

  const columns: ColumnDef<TenantCreditOverview>[] = [
    {
      accessorKey: "tenant_name",
      header: "Tenant",
      cell: ({ row }) => (
        <div>
          <div className="font-medium">{row.original.tenant_name || row.original.tenant_id}</div>
          <div className="font-mono text-xs text-muted-foreground">{row.original.tenant_id}</div>
        </div>
      ),
    },
    {
      accessorKey: "balance_usd",
      header: "Balance",
      cell: ({ row }) => (
        <div className="text-right font-mono tabular-nums">
          <span className={row.original.balance_usd <= 0 ? "text-status-err" : "text-status-ok"}>
            {usd(row.original.balance_usd)}
          </span>
        </div>
      ),
    },
    {
      accessorKey: "spend_30d_usd",
      header: "Spend (30d)",
      cell: ({ row }) => (
        <div className="text-right font-mono tabular-nums">{usd(row.original.spend_30d_usd)}</div>
      ),
    },
    {
      accessorKey: "requests_30d",
      header: "Requests",
      cell: ({ row }) => (
        <div className="text-right font-mono tabular-nums text-muted-foreground">
          {row.original.requests_30d}
        </div>
      ),
    },
    {
      id: "topup",
      enableSorting: false,
      header: () => <span className="block text-right">Top up</span>,
      cell: ({ row }) => (
        <div className="flex items-center justify-end gap-2">
          <input
            aria-label={`Top up ${row.original.tenant_name}`}
            value={amounts[row.original.tenant_id] ?? ""}
            onChange={(e) =>
              setAmounts((a) => ({ ...a, [row.original.tenant_id]: e.target.value }))
            }
            placeholder="$ USD"
            inputMode="decimal"
            className={INPUT}
          />
          <Button
            size="sm"
            disabled={pending !== null}
            onClick={() => topup(row.original.tenant_id)}
          >
            {pending === row.original.tenant_id ? "…" : "Add"}
          </Button>
        </div>
      ),
    },
  ]

  if (rows.length === 0) {
    return <EmptyState title="No tenants yet" description="Tenants appear here once they exist." />
  }

  return (
    <div className="space-y-4">
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}
      {notice ? <AlertBanner tone="success">{notice}</AlertBanner> : null}

      <DataTable
        columns={columns}
        data={rows}
        getRowId={(row) => row.tenant_id}
        searchPlaceholder="Search tenants…"
        searchLabel="Search tenants"
        emptyMessage="No tenants match your search."
      />
    </div>
  )
}
