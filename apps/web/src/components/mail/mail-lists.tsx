"use client"

import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"

import { StatusBadge } from "@/components/ui/status-badge"
import { faTrash } from "@/lib/icons"
import type { MailboxRecord, MailDomainRecord } from "@/lib/types"
import { formatBytes } from "@/lib/utils"

type RemoveFn = (path: string, label: string, key: string) => void

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
}: {
  mailboxes: MailboxRecord[]
  busy: boolean
  onRemove: RemoveFn
}) {
  if (mailboxes.length === 0) return null
  return (
    <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Mailboxes</h2>
        <span className="text-sm text-muted-foreground">{mailboxes.length} shown</span>
      </div>
      <div className="mt-4 overflow-hidden rounded-xl border border-border">
        <table className="min-w-full divide-y divide-border text-sm">
          <thead className="bg-background/60 text-left text-muted-foreground">
            <tr>
              <th className="px-4 py-3 font-medium">Mailbox</th>
              <th className="px-4 py-3 font-medium">Name</th>
              <th className="px-4 py-3 font-medium">Quota</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-border bg-background">
            {mailboxes.map((box) => (
              <tr key={box.username}>
                <td className="px-4 py-3 font-mono">{box.username}</td>
                <td className="px-4 py-3 text-muted-foreground">{box.name || "—"}</td>
                <td className="px-4 py-3 font-mono tabular-nums text-muted-foreground">
                  {formatBytes(box.quota_bytes)}
                </td>
                <td className="px-4 py-3">
                  <StatusBadge value={box.active ? "Active" : "Inactive"} />
                </td>
                <td className="px-4 py-3 text-right">
                  <DeleteButton
                    label={box.username}
                    disabled={busy}
                    onClick={() =>
                      onRemove(`mail/mailboxes/${box.username}`, box.username, `m:${box.username}`)
                    }
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
