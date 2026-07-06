"use client"

import { useRouter } from "next/navigation"
import { useTransition } from "react"

import type { DNSZoneRecord } from "@/lib/types"

/** Dropdown zone picker — navigates to /dns?zone=<id> on change. */
export function ZoneSelector({
  zones,
  selected,
}: {
  zones: DNSZoneRecord[]
  selected: string
}) {
  const router = useRouter()
  const [pending, startTransition] = useTransition()
  const current = zones.find((zone) => zone.id === selected)

  return (
    <div className="flex flex-wrap items-center gap-3">
      <label htmlFor="zone-select" className="text-sm text-muted-foreground">
        Zone
      </label>
      <select
        id="zone-select"
        value={selected}
        disabled={pending || zones.length === 0}
        onChange={(event) => {
          const zoneId = event.target.value
          startTransition(() => router.push(`/dns?zone=${zoneId}`))
        }}
        className="min-w-64 rounded-lg border border-border bg-background px-3 py-2 text-sm font-mono text-foreground focus:border-primary focus:outline-none disabled:opacity-60"
      >
        {zones.length === 0 ? (
          <option value="">No zones</option>
        ) : (
          zones.map((zone) => (
            <option key={zone.id} value={zone.id}>
              {zone.name}
            </option>
          ))
        )}
      </select>
      {current ? (
        <span className="text-sm text-muted-foreground">
          {[current.status, current.account_name].filter(Boolean).join(" · ")}
        </span>
      ) : null}
      {pending ? <span className="text-xs text-muted-foreground">loading…</span> : null}
    </div>
  )
}
