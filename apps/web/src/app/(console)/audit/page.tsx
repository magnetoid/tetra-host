import Link from "next/link"

import { Card } from "@/components/ui/card"
import { EmptyState } from "@/components/ui/empty-state"
import { PageHeader } from "@/components/ui/page-header"
import { StatusBadge } from "@/components/ui/status-badge"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { AuditLogResponse } from "@/lib/types"

const PAGE = 50

function formatWhen(iso: string): string {
  if (!iso) return ""
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString()
}

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

  const log = await fetchBackend<AuditLogResponse>("/audit", {
    token: session.token,
    searchParams: {
      limit: String(PAGE),
      offset: String(offset),
      action: action || undefined,
      actor: actor || undefined,
    },
  }).catch(() => ({ events: [], total: 0, limit: PAGE, offset: 0 }) as AuditLogResponse)

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

      <form method="GET" className="flex flex-wrap items-end gap-3 rounded-2xl border border-border bg-muted p-4">
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
          className="rounded-lg bg-foreground px-4 py-2.5 text-sm font-medium text-background transition-colors hover:bg-foreground/90"
        >
          Filter
        </button>
        {action || actor ? (
          <Link href="/audit" className="px-2 py-2.5 text-sm text-muted-foreground hover:text-foreground">
            Clear
          </Link>
        ) : null}
      </form>

      <Card>
        <div className="flex items-center justify-between">
          <h2 className="font-display text-sm font-semibold">
            {log.total} event{log.total === 1 ? "" : "s"}
          </h2>
          {log.total > 0 ? (
            <span className="font-mono text-xs text-muted-foreground">
              {start}–{end} of {log.total}
            </span>
          ) : null}
        </div>

        <div className="mt-4">
          {log.events.length === 0 ? (
            <EmptyState title="No matching events" description="Audited platform actions appear here." />
          ) : (
            <div className="overflow-x-auto rounded-2xl border border-border">
              <table className="min-w-full divide-y divide-border text-sm">
                <thead className="bg-background/60 text-left text-muted-foreground">
                  <tr>
                    <th className="px-4 py-3 font-medium">When</th>
                    <th className="px-4 py-3 font-medium">Action</th>
                    <th className="px-4 py-3 font-medium">Actor</th>
                    <th className="px-4 py-3 font-medium">Target</th>
                    <th className="px-4 py-3 font-medium">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border bg-background">
                  {log.events.map((e, i) => (
                    <tr key={`${e.action}-${e.created_at}-${i}`}>
                      <td className="whitespace-nowrap px-4 py-3 font-mono text-xs tabular-nums text-muted-foreground">
                        {formatWhen(e.created_at)}
                      </td>
                      <td className="px-4 py-3"><StatusBadge value={e.action} /></td>
                      <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{e.actor_email}</td>
                      <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{e.target}</td>
                      <td className="max-w-xs truncate px-4 py-3 text-xs text-muted-foreground">{e.details}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {log.total > PAGE ? (
          <div className="mt-4 flex items-center justify-between">
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
      </Card>
    </div>
  )
}
