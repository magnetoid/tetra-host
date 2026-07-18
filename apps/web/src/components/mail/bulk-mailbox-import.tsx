"use client"

import { useRouter } from "next/navigation"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { apiFetch, ClientApiError } from "@/lib/client-api"
import { faUpload } from "@/lib/icons"
import type { MailDomainRecord } from "@/lib/types"

type Result = { address: string; password: string; ok: boolean; error?: string }

// Unambiguous alphabet (no 0/O/1/l) for generated passwords.
const ALPHABET = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"

function generatePassword(length = 16): string {
  const bytes = new Uint8Array(length)
  crypto.getRandomValues(bytes)
  return Array.from(bytes, (b) => ALPHABET[b % ALPHABET.length]).join("")
}

/** Parse one line: "local", "local,Display Name", or "local@domain,Display Name". */
function parseLine(line: string): { local: string; name: string } | null {
  const trimmed = line.trim()
  if (!trimmed) return null
  const [addr, ...rest] = trimmed.split(",")
  const local = addr.trim().split("@")[0].trim()
  if (!local) return null
  return { local, name: rest.join(",").trim() }
}

/**
 * Bulk-create mailboxes on a domain — paste one per line. Built for migrations
 * (e.g. moving 62 Plesk mailboxes): generates strong passwords, shown once, so
 * you can hand them out or feed imapsync.
 */
export function BulkMailboxImport({ domains }: { domains: MailDomainRecord[] }) {
  const router = useRouter()
  const [domain, setDomain] = useState(domains[0]?.domain_name ?? "")
  const [text, setText] = useState("")
  const [running, setRunning] = useState(false)
  const [results, setResults] = useState<Result[] | null>(null)
  const [progress, setProgress] = useState(0)

  const entries = text.split("\n").map(parseLine).filter((e): e is { local: string; name: string } => e !== null)

  async function run() {
    if (!domain || entries.length === 0) return
    setRunning(true)
    setResults(null)
    setProgress(0)
    const out: Result[] = []
    for (const [i, entry] of entries.entries()) {
      const address = `${entry.local}@${domain}`
      const password = generatePassword()
      try {
        await apiFetch("/api/proxy/mail/mailboxes", {
          method: "POST",
          body: { local_part: entry.local, domain, password, name: entry.name },
          errorMessage: "Failed",
        })
        out.push({ address, password, ok: true })
      } catch (err) {
        // ClientApiError carries the backend detail; anything else is a network fault.
        const error = err instanceof ClientApiError ? err.message : "Network error"
        out.push({ address, password: "", ok: false, error })
      }
      setProgress(i + 1)
    }
    setResults(out)
    setRunning(false)
    router.refresh()
  }

  const created = results?.filter((r) => r.ok) ?? []

  const inputClass =
    "w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/25"

  return (
    <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
      <h2 className="text-lg font-semibold">Bulk import mailboxes</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        One per line — <span className="font-mono text-xs">local</span> or{" "}
        <span className="font-mono text-xs">local,Display Name</span>. Strong passwords are generated
        and shown once.
      </p>

      <div className="mt-4 grid gap-3 sm:grid-cols-[12rem_1fr]">
        <select
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
          aria-label="Target domain"
          className={inputClass}
        >
          {domains.map((d) => (
            <option key={d.domain_name} value={d.domain_name}>
              @{d.domain_name}
            </option>
          ))}
        </select>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={5}
          placeholder={"marko,Marko T\nsupport,Support\ninfo"}
          aria-label="Mailboxes to import"
          className={`${inputClass} font-mono`}
        />
      </div>

      <div className="mt-3 flex items-center gap-3">
        <Button icon={faUpload} onClick={run} disabled={running || !domain || entries.length === 0}>
          {running ? `Creating ${progress}/${entries.length}…` : `Create ${entries.length || ""} mailbox${entries.length === 1 ? "" : "es"}`.trim()}
        </Button>
        {results ? (
          <span className="text-sm text-muted-foreground">
            {created.length} created · {results.length - created.length} failed
          </span>
        ) : null}
      </div>

      {results ? (
        <div className="mt-4 overflow-hidden rounded-xl border border-border">
          <table className="min-w-full divide-y divide-border text-sm">
            <thead className="bg-background/60 text-left text-muted-foreground">
              <tr>
                <th className="px-4 py-2 font-medium">Mailbox</th>
                <th className="px-4 py-2 font-medium">Password</th>
                <th className="px-4 py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border bg-background">
              {results.map((r) => (
                <tr key={r.address}>
                  <td className="px-4 py-2 font-mono">{r.address}</td>
                  <td className="px-4 py-2 font-mono text-xs">{r.ok ? r.password : "—"}</td>
                  <td className="px-4 py-2">
                    {r.ok ? (
                      <span className="text-status-ok">created</span>
                    ) : (
                      <span className="text-status-err" title={r.error}>
                        {r.error}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {created.length > 0 ? (
        <p className="mt-3 text-xs text-muted-foreground">
          Copy these passwords now — they aren&apos;t stored and won&apos;t be shown again.
        </p>
      ) : null}
    </section>
  )
}
