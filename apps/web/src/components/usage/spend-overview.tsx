"use client"

import { BarList } from "@/components/tremor/bar-list"
import { Card, CardHeader } from "@/components/ui/card"
import { StatCard } from "@/components/ui/stat-card"
import { faChartBar, faChartLine, faGaugeHigh, faLayerGroup } from "@/lib/icons"
import type { AiUsageReport, CreditBalance } from "@/lib/types"
import { formatRelativeLabel } from "@/lib/utils"

/** Compact USD — sub-dollar AI amounts need more precision than invoice-scale figures. */
function usd(value: number): string {
  const abs = Math.abs(value)
  return `$${value.toFixed(abs > 0 && abs < 1 ? 4 : 2)}`
}

export function SpendOverview({
  credit,
  ai,
}: {
  credit: CreditBalance
  ai: AiUsageReport
}) {
  const avgPerRequest = ai.total_requests > 0 ? ai.total_billed_usd / ai.total_requests : 0
  // Naïve month projection from a 30-day window (labelled an estimate).
  const projected = ai.total_billed_usd

  return (
    <div className="space-y-6">
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon={faLayerGroup}
          label="AI credit balance"
          value={usd(credit.balance_usd)}
          hint={credit.balance_usd <= 0 ? "top up to use the AI gateway" : "prepaid"}
          accent={credit.balance_usd <= 0 ? "text-status-err" : "text-status-ok"}
        />
        <StatCard
          icon={faChartBar}
          label="AI spend"
          value={usd(ai.total_billed_usd)}
          hint="last 30 days"
          accent="text-primary"
        />
        <StatCard
          icon={faGaugeHigh}
          label="Requests"
          value={ai.total_requests}
          hint="last 30 days"
          accent="text-status-live"
        />
        <StatCard
          icon={faChartLine}
          label="Avg / request"
          value={usd(avgPerRequest)}
          hint={`~${usd(projected)} projected / mo`}
          accent="text-status-warn"
        />
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Spend by model" action="last 30 days" />
          <div className="mt-4">
            {ai.by_model.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No AI usage yet. Calls through the gateway are metered here.
              </p>
            ) : (
              <BarList
                data={ai.by_model.map((m) => ({
                  name: `${m.model} · ${m.requests}×`,
                  value: Number(m.billed_usd.toFixed(4)),
                }))}
                valueFormatter={(v) => usd(v)}
              />
            )}
          </div>
        </Card>

        <Card>
          <CardHeader title="Wallet activity" action="recent" />
          <div className="mt-4 space-y-2">
            {credit.transactions.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No transactions yet. An admin tops up your prepaid AI credit.
              </p>
            ) : (
              credit.transactions.slice(0, 8).map((t, i) => (
                <div
                  key={`${t.created_at}-${i}`}
                  className="flex items-center justify-between gap-3 rounded-lg border border-border bg-background px-3 py-2 text-sm"
                >
                  <div className="flex min-w-0 items-center gap-2">
                    <span className="rounded-full border border-border px-2 py-0.5 text-[11px] capitalize text-muted-foreground">
                      {t.kind}
                    </span>
                    <span className="truncate font-mono text-xs text-muted-foreground">
                      {t.reference || "—"}
                    </span>
                  </div>
                  <div className="flex shrink-0 items-center gap-3">
                    <span
                      className={`font-mono text-xs tabular-nums ${
                        t.amount_usd >= 0 ? "text-status-ok" : "text-muted-foreground"
                      }`}
                    >
                      {t.amount_usd >= 0 ? "+" : ""}
                      {usd(t.amount_usd)}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {formatRelativeLabel(t.created_at)}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </Card>
      </section>
    </div>
  )
}
