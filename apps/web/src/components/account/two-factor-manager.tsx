"use client"

import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import { useRouter } from "next/navigation"
import { useState } from "react"

import { AlertBanner } from "@/components/ui/alert-banner"
import { Button } from "@/components/ui/button"
import { useAction } from "@/hooks/use-action"
import { apiFetch } from "@/lib/client-api"
import { faCircleCheck, faKey, faUserShield } from "@/lib/icons"
import type { TwoFactorEnableResponse, TwoFactorSetup, TwoFactorStatus } from "@/lib/types"

const INPUT_CLASS =
  "rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/25"

/** Group a base32 secret into 4-char blocks for readable manual entry. */
function formatSecret(secret: string): string {
  return (secret.match(/.{1,4}/g) ?? [secret]).join(" ")
}

/**
 * Self-service TOTP two-factor auth (parity with `tetra 2fa …`). Enrollment is a
 * three-step flow — setup (reveal secret/URI) → verify a code → show one-time
 * backup codes — mirroring the token manager's `useAction` + `apiFetch` pattern.
 */
export function TwoFactorManager({ status }: { status: TwoFactorStatus }) {
  const router = useRouter()
  const { run, pending, error } = useAction()
  const [setup, setSetup] = useState<TwoFactorSetup | null>(null)
  const [code, setCode] = useState("")
  const [backupCodes, setBackupCodes] = useState<string[] | null>(null)
  const [password, setPassword] = useState("")

  function beginSetup() {
    return run(
      async () => {
        const payload = await apiFetch<TwoFactorSetup>("/api/proxy/account/2fa/setup", {
          method: "POST",
          errorMessage: "Could not start two-factor setup.",
        })
        setSetup(payload)
        setBackupCodes(null)
      },
      { key: "setup" },
    )
  }

  async function confirmEnable(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    await run(
      async () => {
        const payload = await apiFetch<TwoFactorEnableResponse>("/api/proxy/account/2fa/enable", {
          method: "POST",
          body: { code },
          errorMessage: "That code was not accepted.",
        })
        setBackupCodes(payload.backup_codes)
        setSetup(null)
        setCode("")
        router.refresh()
      },
      { key: "enable" },
    )
  }

  async function disable(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    await run(
      async () => {
        await apiFetch("/api/proxy/account/2fa/disable", {
          method: "POST",
          body: { password },
          errorMessage: "Could not disable two-factor authentication.",
        })
        setPassword("")
        setBackupCodes(null)
        router.refresh()
      },
      { key: "disable", successMessage: "Two-factor authentication disabled" },
    )
  }

  return (
    <div className="space-y-4">
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}

      {/* One-time backup codes — shown right after enabling. */}
      {backupCodes ? (
        <div className="rounded-lg border border-status-ok/25 bg-status-ok/10 p-4 text-sm">
          <div className="font-medium text-status-ok">
            Two-factor authentication is on. Save these backup codes now — they are shown only once.
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2 font-mono text-xs sm:grid-cols-2">
            {backupCodes.map((bc) => (
              <div key={bc} className="rounded-md border border-border bg-background p-2 text-center">
                {bc}
              </div>
            ))}
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            Each code works once if you lose your authenticator. Store them somewhere safe.
          </p>
        </div>
      ) : null}

      {status.enabled ? (
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-sm text-status-ok">
            <FontAwesomeIcon icon={faCircleCheck} className="h-4 w-4" />
            <span className="font-medium">Enabled</span>
            <span className="text-muted-foreground">
              · {status.backup_codes_remaining} backup code
              {status.backup_codes_remaining === 1 ? "" : "s"} remaining
            </span>
          </div>
          <form onSubmit={disable} className="flex flex-wrap items-end gap-3 rounded-lg border border-border bg-muted p-4">
            <label className="block flex-1 text-sm">
              <span className="mb-2 block text-muted-foreground">
                Confirm your password to turn off two-factor authentication
              </span>
              <input
                type="password"
                aria-label="Account password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Your account password"
                autoComplete="current-password"
                className={`${INPUT_CLASS} w-full`}
                required
              />
            </label>
            <Button type="submit" variant="danger" disabled={pending !== null}>
              {pending === "disable" ? "…" : "Disable 2FA"}
            </Button>
          </form>
        </div>
      ) : setup ? (
        <form onSubmit={confirmEnable} className="space-y-4 rounded-lg border border-border bg-muted p-4">
          <div className="text-sm">
            <p className="text-muted-foreground">
              Add this account to your authenticator app (1Password, Google Authenticator, Authy…),
              then enter the 6-digit code it shows.
            </p>
            <div className="mt-3">
              <span className="text-xs uppercase tracking-wide text-muted-foreground">Setup key</span>
              <div className="mt-1 break-all rounded-md border border-border bg-background p-3 font-mono text-sm tracking-wider">
                {formatSecret(setup.secret)}
              </div>
            </div>
            <details className="mt-2">
              <summary className="cursor-pointer text-xs text-muted-foreground">
                Or copy the otpauth:// setup URI
              </summary>
              <div className="mt-1 break-all rounded-md border border-border bg-background p-2 font-mono text-[11px] text-muted-foreground">
                {setup.otpauth_uri}
              </div>
            </details>
          </div>
          <label className="block text-sm">
            <span className="mb-2 block text-muted-foreground">6-digit code</span>
            <input
              inputMode="numeric"
              autoComplete="one-time-code"
              aria-label="Verification code"
              value={code}
              onChange={(event) => setCode(event.target.value)}
              placeholder="123 456"
              className={`${INPUT_CLASS} w-40 font-mono tracking-widest`}
              required
            />
          </label>
          <div className="flex gap-2">
            <Button type="submit" icon={faKey} disabled={pending !== null}>
              {pending === "enable" ? "…" : "Verify & enable"}
            </Button>
            <Button type="button" variant="ghost" onClick={() => setSetup(null)} disabled={pending !== null}>
              Cancel
            </Button>
          </div>
        </form>
      ) : (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="max-w-lg text-sm text-muted-foreground">
            Add a second step to every sign-in — the panel, the console, and{" "}
            <span className="font-mono">tetra login</span> will ask for a code from your authenticator
            app. You&apos;ll get one-time backup codes in case you lose your device.
          </p>
          <Button icon={faUserShield} onClick={beginSetup} disabled={pending !== null}>
            {pending === "setup" ? "…" : "Enable 2FA"}
          </Button>
        </div>
      )}
    </div>
  )
}
