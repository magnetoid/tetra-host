"use client"

import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"

import { StatusBadge } from "@/components/ui/status-badge"
import { faSliders, faTrash } from "@/lib/icons"
import type { MailboxRecord, MailDomainRecord } from "@/lib/types"
import { cn, formatBytes } from "@/lib/utils"

type RemoveFn = (path: string, label: string, key: string) => void

/** Compact used/total quota bar. Colour escalates as the mailbox fills up. */
function QuotaBar({ used, total, percent }: { used: number; total: number; percent: number }) {
  const tone =
    percent >= 90 ? "bg-status-err" : percent >= 75 ? "bg-status-warn" : "bg-primary"
  return (
    <div className="min-w-[9rem]">
      <div className="flex items-baseline justify-between gap-2 text-xs">
        <span className="font-mono tabular-nums text-muted-foreground">
          {formatBytes(used)}
          {total > 0 ? ` / ${formatBytes(total)}` : ""}
        </span>
        {total > 0 ? (
          <span className="font-mono tabular-nums text-muted-foreground">{percent}%</span>
        ) : (
          <span className="text-muted-foreground">∞</span>
        )}
      </div>
      {total > 0 ? (
        <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-border">
          <div
            className={cn("h-full rounded-full transition-all", tone)}
            style={{ width: `${Math.max(2, percent)}%` }}
          />
        </div>
      ) : null}
    </div>
  )
}

function DeleteButton({
  label,
  onClick,
  disabled,
}: {
  label: string
  onClick: () => void
  disabled: boolean
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="rounded-lg border border-border p-2 text-muted-foreground transition-colors hover:border-status-err/40 hover:text-status-err disabled:opacity-50"
      aria-label={`Delete ${label}`}
    >
      <FontAwesomeIcon icon={faTrash} className="h-3.5 w-3.5" />
    </button>
  )
}

export function MailDomainsList({
  domains,
  busy,
  onRemove,
}: {
  domains: MailDomainRecord[]
  busy: boolean
  onRemove: RemoveFn
}) {
  return (
    <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Mail domains</h2>
        <span className="text-sm text-muted-foreground">{domains.length} total</span>
      </div>
      <div className="mt-4 space-y-2">
        {domains.length === 0 ? (
          <p className="text-sm text-muted-foreground">No mail domains yet — add one above.</p>
        ) : (
          domains.map((d) => (
            <div
              key={d.domain_name}
              className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-background p-4"
            >
              <div>
                <div className="font-mono font-medium">{d.domain_name}</div>
                <div className="mt-0.5 text-xs text-muted-foreground">
                  {d.mailboxes} mailboxes · {d.aliases} aliases
                </div>
              </div>
              <div className="flex items-center gap-2">
                <StatusBadge value={d.active ? "Active" : "Inactive"} />
                <DeleteButton
                  label={d.domain_name}
                  disabled={busy}
                  onClick={() =>
                    onRemove(`mail/domains/${d.domain_name}`, d.domain_name, `d:${d.domain_name}`)
                  }
                />
              </div>
            </div>
          ))
        )}
      </div>
    </section>
  )
}

export function MailboxesTable({
  mailboxes,
  busy,
  onRemove,
  onManage,
  activeUsername,
}: {
  mailboxes: MailboxRecord[]
  busy: boolean
  onRemove: RemoveFn
  /** Open the management panel (edit + app passwords) for a mailbox. */
  onManage?: (box: MailboxRecord) => void
  /** Username whose panel is currently open (row is highlighted). */
  activeUsername?: string | null
}) {
  if (mailboxes.length === 0) return null
  return (
    <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Mailboxes</h2>
        <span className="text-sm text-muted-foreground">{mailboxes.length} shown</span>
      </div>
      <div className="mt-4 overflow-x-auto rounded-xl border border-border">
        <table className="min-w-full divide-y divide-border text-sm">
          <thead className="bg-background/60 text-left text-muted-foreground">
            <tr>
              <th className="px-4 py-3 font-medium">Mailbox</th>
              <th className="px-4 py-3 font-medium">Name</th>
              <th className="px-4 py-3 font-medium">Storage</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-border bg-background">
            {mailboxes.map((box) => (
              <tr
                key={box.username}
                className={cn(activeUsername === box.username && "bg-accent/50")}
              >
                <td className="px-4 py-3 font-mono">{box.username}</td>
                <td className="px-4 py-3 text-muted-foreground">{box.name || "—"}</td>
                <td className="px-4 py-3">
                  <QuotaBar
                    used={box.quota_used_bytes}
                    total={box.quota_bytes}
                    percent={box.percent_used}
                  />
                </td>
                <td className="px-4 py-3">
                  <StatusBadge value={box.active ? "Active" : "Inactive"} />
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center justify-end gap-2">
                    {onManage ? (
                      <button
                        type="button"
                        onClick={() => onManage(box)}
                        disabled={busy}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-2 text-xs font-medium text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground disabled:opacity-50"
                        aria-label={`Manage ${box.username}`}
                      >
                        <FontAwesomeIcon icon={faSliders} className="h-3.5 w-3.5" />
                        Manage
                      </button>
                    ) : null}
                    <DeleteButton
                      label={box.username}
                      disabled={busy}
                      onClick={() =>
                        onRemove(`mail/mailboxes/${box.username}`, box.username, `m:${box.username}`)
                      }
                    />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
