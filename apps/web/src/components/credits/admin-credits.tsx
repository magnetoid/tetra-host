"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"

import { AlertBanner } from "@/components/ui/alert-banner"
import { Button } from "@/components/ui/button"
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

  if (rows.length === 0) {
    return <EmptyState title="No tenants yet" description="Tenants appear here once they exist." />
  }

  return (
    <div className="space-y-4">
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}
      {notice ? <AlertBanner tone="success">{notice}</AlertBanner> : null}

      <div className="overflow-x-auto rounded-2xl border border-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted text-left text-xs uppercase tracking-wider text-muted-foreground">
              <th className="px-4 py-3 font-medium">Tenant</th>
              <th className="px-4 py-3 text-right font-medium">Balance</th>
              <th className="px-4 py-3 text-right font-medium">Spend (30d)</th>
              <th className="px-4 py-3 text-right font-medium">Requests</th>
              <th className="px-4 py-3 text-right font-medium">Top up</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.tenant_id} className="border-b border-border last:border-0">
                <td className="px-4 py-3">
                  <div className="font-medium">{r.tenant_name || r.tenant_id}</div>
                  <div className="font-mono text-xs text-muted-foreground">{r.tenant_id}</div>
                </td>
                <td className="px-4 py-3 text-right font-mono tabular-nums">
                  <span className={r.balance_usd <= 0 ? "text-status-err" : "text-status-ok"}>
                    {usd(r.balance_usd)}
                  </span>
                </td>
                <td className="px-4 py-3 text-right font-mono tabular-nums">{usd(r.spend_30d_usd)}</td>
                <td className="px-4 py-3 text-right font-mono tabular-nums text-muted-foreground">
                  {r.requests_30d}
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center justify-end gap-2">
                    <input
                      aria-label={`Top up ${r.tenant_name}`}
                      value={amounts[r.tenant_id] ?? ""}
                      onChange={(e) => setAmounts((a) => ({ ...a, [r.tenant_id]: e.target.value }))}
                      placeholder="$ USD"
                      inputMode="decimal"
                      className={INPUT}
                    />
                    <Button
                      size="sm"
                      disabled={pending !== null}
                      onClick={() => topup(r.tenant_id)}
                    >
                      {pending === r.tenant_id ? "…" : "Add"}
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
