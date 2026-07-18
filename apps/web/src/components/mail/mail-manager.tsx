"use client"

import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import { useRouter } from "next/navigation"
import { useState } from "react"

import { AlertBanner } from "@/components/ui/alert-banner"
import { Button } from "@/components/ui/button"
import { StatusBadge } from "@/components/ui/status-badge"
import { faCircleCheck, faPlus, faTrash, faWandSparkles } from "@/lib/icons"
import type { MailDomainCreateResult, MailDomainRecord, MailboxRecord } from "@/lib/types"
import { formatBytes } from "@/lib/utils"

const DNS_DOT: Record<string, string> = {
  created: "bg-status-ok",
  skipped: "bg-status-warn",
  failed: "bg-status-err",
}

/**
 * Interactive mail management. Adding a domain provisions DKIM + wires
 * MX/SPF/DKIM/DMARC in Cloudflare automatically (backend does the work) — so any
 * domain you already run on an app can get mail in one click.
 */
export function MailManager({
  domains,
  mailboxes,
  appDomains,
}: {
  domains: MailDomainRecord[]
  mailboxes: MailboxRecord[]
  /** Distinct domains you already host on apps — offered as one-click quick-picks. */
  appDomains: string[]
}) {
  const router = useRouter()
  const [pending, setPending] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [report, setReport] = useState<MailDomainCreateResult | null>(null)

  const [domain, setDomain] = useState("")
  const [local, setLocal] = useState("")
  const [mbDomain, setMbDomain] = useState(domains[0]?.domain_name ?? "")
  const [password, setPassword] = useState("")
  const [fullName, setFullName] = useState("")

  const mailedDomains = new Set(domains.map((d) => d.domain_name))
  const quickPicks = appDomains.filter((d) => !mailedDomains.has(d))

  async function post(path: string, body: unknown, key: string) {
    setError(null)
    setPending(key)
    try {
      const res = await fetch(`/api/proxy/${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })
      const payload = await res.json().catch(() => ({}))
      if (!res.ok) {
        setError(payload.detail ?? "Request failed.")
        return null
      }
      router.refresh()
      return payload
    } catch {
      setError("Network error — please retry.")
      return null
    } finally {
      setPending(null)
    }
  }

  async function addDomain(event: React.FormEvent) {
    event.preventDefault()
    setReport(null)
    const result = await post("mail/domains", { domain: domain.trim() }, "domain")
    if (result) {
      setReport(result as MailDomainCreateResult)
      setDomain("")
    }
  }

  async function addMailbox(event: React.FormEvent) {
    event.preventDefault()
    const result = await post(
      "mail/mailboxes",
      { local_part: local.trim(), domain: mbDomain, password, name: fullName.trim() },
      "mailbox",
    )
    if (result) {
      setLocal("")
      setPassword("")
      setFullName("")
    }
  }

  async function remove(path: string, label: string, key: string) {
    if (!window.confirm(`Delete ${label}? This can't be undone.`)) return
    setError(null)
    setPending(key)
    try {
      const res = await fetch(`/api/proxy/${path}`, { method: "DELETE" })
      if (!res.ok) {
        const payload = await res.json().catch(() => ({}))
        setError(payload.detail ?? "Delete failed.")
        return
      }
      router.refresh()
    } finally {
      setPending(null)
    }
  }

  const inputClass =
    "w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/25"

  return (
    <div className="space-y-6">
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}

      {/* Add a mail domain — the automated bit */}
      <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
        <div className="flex items-center gap-2">
          <FontAwesomeIcon icon={faWandSparkles} className="h-4 w-4 text-primary" />
          <h2 className="text-lg font-semibold">Add a mail domain</h2>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          Provisions DKIM and wires MX, SPF, DKIM, and DMARC in Cloudflare automatically.
        </p>

        {quickPicks.length > 0 ? (
          <div className="mt-4">
            <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Enable mail for an app domain
            </div>
            <div className="mt-2 flex flex-wrap gap-2">
              {quickPicks.map((d) => (
                <button
                  key={d}
                  type="button"
                  onClick={() => setDomain(d)}
                  className="rounded-lg border border-border bg-background px-3 py-1.5 font-mono text-xs transition-colors hover:border-primary/40 hover:bg-accent"
                >
                  {d}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        <form onSubmit={addDomain} className="mt-4 flex flex-wrap gap-2">
          <input
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
            placeholder="example.com"
            className={`${inputClass} max-w-xs flex-1`}
            aria-label="Mail domain"
          />
          <Button type="submit" icon={faPlus} disabled={pending !== null || !domain.trim()}>
            {pending === "domain" ? "Adding…" : "Add domain"}
          </Button>
        </form>

        {report ? <DnsReport report={report} /> : null}
      </section>

      {/* Add a mailbox */}
      {domains.length > 0 ? (
        <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
          <h2 className="text-lg font-semibold">Add a mailbox</h2>
          <form onSubmit={addMailbox} className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <input
              value={local}
              onChange={(e) => setLocal(e.target.value)}
              placeholder="you"
              aria-label="Mailbox local part"
              className={inputClass}
            />
            <select
              value={mbDomain}
              onChange={(e) => setMbDomain(e.target.value)}
              aria-label="Mailbox domain"
              className={inputClass}
            >
              {domains.map((d) => (
                <option key={d.domain_name} value={d.domain_name}>
                  @{d.domain_name}
                </option>
              ))}
            </select>
            <input
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Display name"
              aria-label="Display name"
              className={inputClass}
            />
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Password"
              aria-label="Mailbox password"
              className={inputClass}
            />
            <Button
              type="submit"
              icon={faPlus}
              disabled={pending !== null || !local.trim() || !mbDomain || password.length < 8}
            >
              {pending === "mailbox" ? "Adding…" : "Add mailbox"}
            </Button>
          </form>
          <p className="mt-2 text-xs text-muted-foreground">Password must be at least 8 characters.</p>
        </section>
      ) : null}

      {/* Domains */}
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
                  <button
                    type="button"
                    onClick={() => remove(`mail/domains/${d.domain_name}`, d.domain_name, `d:${d.domain_name}`)}
                    disabled={pending !== null}
                    className="rounded-lg border border-border p-2 text-muted-foreground transition-colors hover:border-status-err/40 hover:text-status-err disabled:opacity-50"
                    aria-label={`Delete ${d.domain_name}`}
                  >
                    <FontAwesomeIcon icon={faTrash} className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </section>

      {/* Mailboxes */}
      {mailboxes.length > 0 ? (
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
                      <button
                        type="button"
                        onClick={() => remove(`mail/mailboxes/${box.username}`, box.username, `m:${box.username}`)}
                        disabled={pending !== null}
                        className="rounded-lg border border-border p-2 text-muted-foreground transition-colors hover:border-status-err/40 hover:text-status-err disabled:opacity-50"
                        aria-label={`Delete ${box.username}`}
                      >
                        <FontAwesomeIcon icon={faTrash} className="h-3.5 w-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </div>
  )
}

function DnsReport({ report }: { report: MailDomainCreateResult }) {
  return (
    <div className="mt-5 rounded-xl border border-border bg-background p-4">
      <div className="flex items-center gap-2 text-sm font-medium text-status-ok">
        <FontAwesomeIcon icon={faCircleCheck} className="h-4 w-4" />
        {report.domain} is ready
        {report.dns_zone ? (
          <span className="font-normal text-muted-foreground">· DNS in {report.dns_zone}</span>
        ) : null}
      </div>

      {report.dns_records.length > 0 ? (
        <ul className="mt-3 space-y-1.5">
          {report.dns_records.map((r) => (
            <li key={`${r.record_type}-${r.name}`} className="flex items-center gap-2 text-xs">
              <span className={`size-2 shrink-0 rounded-full ${DNS_DOT[r.status] ?? "bg-muted-foreground"}`} />
              <span className="font-mono font-medium">{r.record_type}</span>
              <span className="truncate font-mono text-muted-foreground">{r.name}</span>
              <span className="ml-auto capitalize text-muted-foreground">{r.status}</span>
            </li>
          ))}
        </ul>
      ) : null}

      {report.dkim_txt ? (
        <div className="mt-3">
          <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            DKIM ({report.dkim_name})
          </div>
          <pre className="mt-1 overflow-x-auto rounded-lg border border-border bg-card p-3 font-mono text-[11px] leading-relaxed">
            {report.dkim_txt}
          </pre>
        </div>
      ) : null}

      {report.relay_assigned ? (
        <p className="mt-3 text-xs text-muted-foreground">Outbound relay assigned for deliverability.</p>
      ) : null}
    </div>
  )
}
