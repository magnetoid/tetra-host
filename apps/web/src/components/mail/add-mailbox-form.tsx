"use client"

import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { faPlus } from "@/lib/icons"
import type { MailDomainRecord } from "@/lib/types"

export type MailboxDraft = {
  local_part: string
  domain: string
  password: string
  name: string
}

/** Create-a-mailbox form, scoped to one of the tenant's mail domains. */
export function AddMailboxForm({
  domains,
  busy,
  onAdd,
}: {
  domains: MailDomainRecord[]
  busy: boolean
  onAdd: (draft: MailboxDraft) => Promise<boolean>
}) {
  const [local, setLocal] = useState("")
  const [mbDomain, setMbDomain] = useState(domains[0]?.domain_name ?? "")
  const [password, setPassword] = useState("")
  const [fullName, setFullName] = useState("")

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    const ok = await onAdd({
      local_part: local.trim(),
      domain: mbDomain,
      password,
      name: fullName.trim(),
    })
    if (ok) {
      setLocal("")
      setPassword("")
      setFullName("")
    }
  }

  return (
    <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
      <h2 className="text-lg font-semibold">Add a mailbox</h2>
      <form onSubmit={submit} className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <Input
          value={local}
          onChange={(e) => setLocal(e.target.value)}
          placeholder="you"
          aria-label="Mailbox local part"
        />
        <select
          value={mbDomain}
          onChange={(e) => setMbDomain(e.target.value)}
          aria-label="Mailbox domain"
          className="rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none transition focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/40"
        >
          {domains.map((d) => (
            <option key={d.domain_name} value={d.domain_name}>
              @{d.domain_name}
            </option>
          ))}
        </select>
        <Input
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          placeholder="Display name"
          aria-label="Display name"
        />
        <Input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          aria-label="Mailbox password"
        />
        <Button
          type="submit"
          icon={faPlus}
          disabled={busy || !local.trim() || !mbDomain || password.length < 8}
        >
          {busy ? "Adding…" : "Add mailbox"}
        </Button>
      </form>
      <p className="mt-2 text-xs text-muted-foreground">Password must be at least 8 characters.</p>
    </section>
  )
}
