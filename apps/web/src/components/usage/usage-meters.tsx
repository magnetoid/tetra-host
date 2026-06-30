"use client"

import { Card, CardHeader } from "@/components/ui/card"
import type { Usage } from "@/lib/types"

function pct(used: number, limit: number): number {
  if (limit <= 0) return 0
  return Math.min(100, Math.round((used / limit) * 100))
}

function MeterBar({
  label,
  used,
  limit,
  unit,
  enforced,
}: {
  label: string
  used: number
  limit: number
  unit?: string
  enforced: boolean
}) {
  const fill = pct(used, limit)
  const overLimit = used > limit && limit > 0
  const barColor = overLimit
    ? "bg-red-500"
    : enforced
      ? "bg-primary"
      : "bg-zinc-500"

  const usedLabel = unit ? `${used.toLocaleString()} ${unit}` : used.toLocaleString()
  const limitLabel = unit ? `${limit.toLocaleString()} ${unit}` : limit.toLocaleString()

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-zinc-200">{label}</span>
          {!enforced && (
            <span className="inline-flex items-center rounded-full bg-zinc-800 px-2 py-0.5 text-[11px] font-medium text-zinc-400">
              advisory — not yet enforced
            </span>
          )}
          {enforced && (
            <span className="inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-medium text-primary">
              enforced
            </span>
          )}
        </div>
        <span className="shrink-0 text-xs text-zinc-400">
          {usedLabel} / {limitLabel}
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-zinc-800">
        <div
          className={`h-full rounded-full transition-all ${barColor}`}
          style={{ width: `${fill}%` }}
          aria-label={`${fill}% used`}
        />
      </div>
    </div>
  )
}

export function UsageMeters({ usage }: { usage: Usage }) {
  const isEnforced = (dim: string) => usage.enforced.includes(dim)

  return (
    <Card>
      <CardHeader
        title="Quota usage"
        action={
          usage.plan_key ? (
            <span className="font-mono text-xs text-zinc-400">{usage.plan_key}</span>
          ) : undefined
        }
      />
      <div className="mt-6 space-y-5">
        <MeterBar
          label="Apps"
          used={usage.apps_used}
          limit={usage.apps_limit}
          enforced={isEnforced("apps")}
        />
        <MeterBar
          label="CPU"
          used={usage.cpu_millicores_used}
          limit={usage.cpu_millicores_limit}
          unit="m"
          enforced={isEnforced("cpu_millicores")}
        />
        <MeterBar
          label="Memory"
          used={usage.mem_mb_used}
          limit={usage.mem_mb_limit}
          unit="MB"
          enforced={isEnforced("mem_mb")}
        />
        <MeterBar
          label="Disk"
          used={usage.disk_mb_used}
          limit={usage.disk_mb_limit}
          unit="MB"
          enforced={isEnforced("disk_mb")}
        />
        <MeterBar
          label="Domains"
          used={usage.domains_used}
          limit={usage.domains_limit}
          enforced={isEnforced("domains")}
        />
      </div>
    </Card>
  )
}
