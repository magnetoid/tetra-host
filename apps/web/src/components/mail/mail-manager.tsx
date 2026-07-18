"use client"

import { useState } from "react"

import { AddDomainForm } from "@/components/mail/add-domain-form"
import { AddMailboxForm, type MailboxDraft } from "@/components/mail/add-mailbox-form"
import { MailboxesTable, MailDomainsList } from "@/components/mail/mail-lists"
import { MailboxPanel } from "@/components/mail/mailbox-panel"
import { AlertBanner } from "@/components/ui/alert-banner"
import { useAction } from "@/hooks/use-action"
import { apiFetch } from "@/lib/client-api"
import type { MailDomainCreateResult, MailboxRecord, MailDomainRecord } from "@/lib/types"

/**
 * Mail management orchestrator. Adding a domain provisions DKIM + wires
 * MX/SPF/DKIM/DMARC in Cloudflare automatically (backend does the work). Thin
 * shell: state + mutations here, presentation in the mail/* child components.
 */
export function MailManager({
  domains,
  mailboxes,
  appDomains,
  webmailBase = "",
}: {
  domains: MailDomainRecord[]
  mailboxes: MailboxRecord[]
  /** Distinct domains you already host on apps — offered as one-click quick-picks. */
  appDomains: string[]
  /** Panel public origin for the OIDC "Open webmail" launch; "" hides the button. */
  webmailBase?: string
}) {
  const { run, pending, error } = useAction()
  const [report, setReport] = useState<MailDomainCreateResult | null>(null)
  const [managed, setManaged] = useState<string | null>(null)

  const mailedDomains = new Set(domains.map((d) => d.domain_name))
  const quickPicks = appDomains.filter((d) => !mailedDomains.has(d))
  const busy = pending !== null
  // Re-resolve the managed mailbox from the latest server data so its panel
  // reflects edits after router.refresh(); drop it if the mailbox is gone.
  const managedMailbox = managed ? (mailboxes.find((m) => m.username === managed) ?? null) : null

  async function addDomain(domain: string) {
    if (!domain) return false
    setReport(null)
    return run(
      async () => {
        const result = await apiFetch<MailDomainCreateResult>("/api/proxy/mail/domains", {
          method: "POST",
          body: { domain },
          errorMessage: "Could not add mail domain.",
        })
        setReport(result)
      },
      { key: "domain", successMessage: "Mail domain added" },
    )
  }

  async function addMailbox(draft: MailboxDraft) {
    return run(
      () =>
        apiFetch("/api/proxy/mail/mailboxes", {
          method: "POST",
          body: draft,
          errorMessage: "Could not add mailbox.",
        }),
      { key: "mailbox", successMessage: "Mailbox added" },
    )
  }

  function remove(path: string, label: string, key: string) {
    if (!window.confirm(`Delete ${label}? This can't be undone.`)) return
    void run(
      () =>
        apiFetch(`/api/proxy/${path}`, { method: "DELETE", errorMessage: "Could not delete." }),
      { key, successMessage: `${label} deleted` },
    )
  }

  return (
    <div className="space-y-6">
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}

      <AddDomainForm
        quickPicks={quickPicks}
        report={report}
        busy={pending === "domain"}
        onAdd={addDomain}
      />

      {domains.length > 0 ? (
        <AddMailboxForm domains={domains} busy={pending === "mailbox"} onAdd={addMailbox} />
      ) : null}

      <MailDomainsList domains={domains} busy={busy} onRemove={remove} />
      <MailboxesTable
        mailboxes={mailboxes}
        busy={busy}
        onRemove={remove}
        onManage={(box) => setManaged(box.username)}
        activeUsername={managedMailbox?.username ?? null}
      />

      {managedMailbox ? (
        <MailboxPanel
          mailbox={managedMailbox}
          webmailBase={webmailBase}
          onClose={() => setManaged(null)}
        />
      ) : null}
    </div>
  )
}
