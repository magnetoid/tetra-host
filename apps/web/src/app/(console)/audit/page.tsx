import Link from "next/link"

import { AuditEventsTable } from "@/components/audit/audit-events-table"
import { Card } from "@/components/ui/card"
import { DegradedBanner } from "@/components/ui/degraded-banner"
import { PageHeader } from "@/components/ui/page-header"
import { requireConsoleSession } from "@/lib/auth"
import { degradedSources, fetchDegraded } from "@/lib/fetch-degraded"
import type { AuditLogResponse } from "@/lib/types"

const PAGE = 50

type AuditPageProps = {
  searchParams: Promise<{ action?: string; actor?: string; offset?: string }>
}

export default async function AuditPage({ searchParams }: AuditPageProps) {
  const session = await requireConsoleSession()

  if (session.admin.role !== "platform_admin") {
    return (
      <div className="space-y-6">
        <PageHeader eyebrow="Platform operations" title="Audit log" description="Every audited platform action." />
        <Card>
          <p className="text-sm text-muted-foreground">
            The audit log is restricted to platform administrators.
          </p>
        </Card>
      </div>
    )
  }

  const params = await searchParams
  const action = params.action?.trim() ?? ""
  const actor = params.actor?.trim() ?? ""
  const offset = Math.max(0, Number(params.offset) || 0)

  const logRes = await fetchDegraded<AuditLogResponse>(
    "/audit",
    "Audit log",
    { events: [], total: 0, limit: PAGE, offset: 0 },
    {
      token: session.token,
      searchParams: {
        limit: String(PAGE),
        offset: String(offset),
        action: action || undefined,
        actor: actor || undefined,
      },
    },
  )
  const log = logRes.data

  const start = log.total === 0 ? 0 : offset + 1
  const end = Math.min(offset + log.events.length, log.total)
  const q = (o: number) => {
    const sp = new URLSearchParams()
    if (action) sp.set("action", action)
    if (actor) sp.set("actor", actor)
    if (o > 0) sp.set("offset", String(o))
    const s = sp.toString()
    return s ? `/audit?${s}` : "/audit"
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Platform operations"
        title="Audit log"
        description="Every audited platform action — approvals, suspensions, provisioning, and more. Platform-admin only."
      />

      <DegradedBanner sources={degradedSources([logRes])} />

      <form method="GET" className="flex flex-wrap items-end gap-3 rounded-lg border border-border bg-muted p-4">
        <label className="block text-sm">
          <span className="mb-2 block text-muted-foreground">Action</span>
          <input
            name="action"
            defaultValue={action}
            placeholder="e.g. tenant.approve"
            className="rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/25"
          />
        </label>
        <label className="block text-sm">
          <span className="mb-2 block text-muted-foreground">Actor email</span>
          <input
            name="actor"
            defaultValue={actor}
            placeholder="admin@…"
            className="rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/25"
          />
        </label>
        <button
          type="submit"
          className="rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90"
        >
          Filter
        </button>
        {action || actor ? (
          <Link href="/audit" className="px-2 py-2.5 text-sm text-muted-foreground hover:text-foreground">
            Clear
          </Link>
        ) : null}
      </form>

      <div className="space-y-4">
        <AuditEventsTable
          events={log.events}
          title={`${log.total} event${log.total === 1 ? "" : "s"}`}
          action={
            log.total > 0 ? (
              <span className="font-mono text-xs text-muted-foreground">
                {start}–{end} of {log.total}
              </span>
            ) : undefined
          }
          showDetails
          emptyMessage="No matching events. Audited platform actions appear here."
        />

        {log.total > PAGE ? (
          <div className="flex items-center justify-between">
            {offset > 0 ? (
              <Link href={q(Math.max(0, offset - PAGE))} className="rounded-lg border border-border px-3 py-1.5 text-sm transition-colors hover:bg-accent">
                ← Newer
              </Link>
            ) : <span />}
            {end < log.total ? (
              <Link href={q(offset + PAGE)} className="rounded-lg border border-border px-3 py-1.5 text-sm transition-colors hover:bg-accent">
                Older →
              </Link>
            ) : <span />}
          </div>
        ) : null}
      </div>
    </div>
  )
}
