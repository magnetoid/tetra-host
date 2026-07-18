"use client"

import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import Link from "next/link"
import { useState } from "react"

import { AlertBanner } from "@/components/ui/alert-banner"
import { Button } from "@/components/ui/button"
import { useAction } from "@/hooks/use-action"
import { apiFetch } from "@/lib/client-api"
import { faCircleCheck, faEnvelope } from "@/lib/icons"

/**
 * One-click mail for an app's own domain: provisions the Mailcow domain and
 * auto-wires MX/SPF/DKIM/DMARC (backend), right where you manage the domain.
 */
export function EnableMailButton({ domain, enabled }: { domain: string; enabled: boolean }) {
  const { run, pending, error } = useAction()
  const [done, setDone] = useState(enabled)

  if (done) {
    return (
      <div className="flex items-center gap-2 text-sm">
        <span className="inline-flex items-center gap-1.5 text-status-ok">
          <FontAwesomeIcon icon={faCircleCheck} className="h-3.5 w-3.5" />
          Mail enabled
        </span>
        <Link href="/mail" className="text-muted-foreground transition-colors hover:text-foreground">
          Manage mailboxes →
        </Link>
      </div>
    )
  }

  async function enable() {
    const ok = await run(
      () =>
        apiFetch("/api/proxy/mail/domains", {
          method: "POST",
          body: { domain },
          errorMessage: "Couldn't enable mail for this domain.",
        }),
      { key: "enable", successMessage: "Mail enabled" },
    )
    if (ok) setDone(true)
  }

  return (
    <div className="space-y-2">
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}
      <Button icon={faEnvelope} onClick={enable} disabled={pending !== null}>
        {pending !== null ? "Enabling…" : "Enable mail"}
      </Button>
      <p className="text-xs text-muted-foreground">
        Creates a mailbox domain and wires MX, SPF, DKIM, and DMARC automatically.
      </p>
    </div>
  )
}
