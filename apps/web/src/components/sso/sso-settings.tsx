"use client"

import { useState } from "react"

import { AlertBanner } from "@/components/ui/alert-banner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { useAction } from "@/hooks/use-action"
import { apiFetch } from "@/lib/client-api"
import type { SSOConfig } from "@/lib/types"

const INPUT_CLASS =
  "w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/25"

function ReadonlyField({ label, value }: { label: string; value: string }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block text-xs text-muted-foreground">{label}</span>
      <input
        readOnly
        value={value}
        onFocus={(event) => event.currentTarget.select()}
        className={`${INPUT_CLASS} font-mono text-xs`}
      />
    </label>
  )
}

export function SSOSettings({
  config,
  tenantSlug,
  origin,
}: {
  config: SSOConfig
  tenantSlug: string
  origin: string
}) {
  const { run, pending, error } = useAction()
  const [providerLabel, setProviderLabel] = useState(config.provider_label || "OpenID Connect")
  const [issuer, setIssuer] = useState(config.issuer)
  const [clientId, setClientId] = useState(config.client_id)
  const [clientSecret, setClientSecret] = useState("")
  const [allowedDomains, setAllowedDomains] = useState(config.allowed_domains)
  const [defaultRole, setDefaultRole] = useState(config.default_role || "member")
  const [enabled, setEnabled] = useState(config.enabled)
  const [saved, setSaved] = useState(false)

  const callbackUrl = `${origin}/auth/sso/callback`
  const loginUrl = `${origin}/auth/sso/${tenantSlug}/login`

  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaved(false)
    const ok = await run(
      () =>
        apiFetch("/api/proxy/sso", {
          method: "PUT",
          body: {
            provider_label: providerLabel,
            issuer,
            client_id: clientId,
            client_secret: clientSecret, // blank keeps the stored secret
            allowed_domains: allowedDomains,
            default_role: defaultRole,
            enabled,
          },
          errorMessage: "Could not save SSO settings.",
        }),
      { key: "save" },
    )
    if (ok) {
      setClientSecret("")
      setSaved(true)
    }
  }

  function disable() {
    return run(
      () =>
        apiFetch("/api/proxy/sso", {
          method: "DELETE",
          errorMessage: "Could not remove the SSO configuration.",
        }),
      { key: "disable", successMessage: "SSO configuration removed" },
    )
  }

  return (
    <div className="rounded-lg border border-border bg-muted p-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-display text-lg font-semibold">Single sign-on</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Let your team sign in through your OpenID Connect identity provider.
          </p>
        </div>
        {config.enabled ? (
          <Badge variant="success">enabled</Badge>
        ) : config.configured ? (
          <Badge variant="outline">configured</Badge>
        ) : (
          <Badge variant="secondary">off</Badge>
        )}
      </div>

      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}
      {saved ? <AlertBanner tone="success">SSO settings saved.</AlertBanner> : null}

      {/* Register these two URLs with the IdP + share the login link. */}
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <ReadonlyField label="Redirect / callback URL (register at your IdP)" value={callbackUrl} />
        <ReadonlyField label="Member sign-in URL (share with your team)" value={loginUrl} />
      </div>

      <form onSubmit={save} className="mt-5 space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block text-sm">
            <span className="mb-1 block text-xs text-muted-foreground">Provider name</span>
            <input
              aria-label="Provider name"
              value={providerLabel}
              onChange={(event) => setProviderLabel(event.target.value)}
              className={INPUT_CLASS}
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-xs text-muted-foreground">Issuer URL</span>
            <input
              aria-label="Issuer URL"
              value={issuer}
              onChange={(event) => setIssuer(event.target.value)}
              placeholder="https://accounts.google.com"
              className={INPUT_CLASS}
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-xs text-muted-foreground">Client ID</span>
            <input
              aria-label="Client ID"
              value={clientId}
              onChange={(event) => setClientId(event.target.value)}
              className={INPUT_CLASS}
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-xs text-muted-foreground">
              Client secret {config.has_secret ? "(stored — leave blank to keep)" : ""}
            </span>
            <input
              aria-label="Client secret"
              type="password"
              value={clientSecret}
              onChange={(event) => setClientSecret(event.target.value)}
              placeholder={config.has_secret ? "••••••••" : ""}
              className={INPUT_CLASS}
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-xs text-muted-foreground">
              Allowed email domains (comma-separated; blank = any)
            </span>
            <input
              aria-label="Allowed domains"
              value={allowedDomains}
              onChange={(event) => setAllowedDomains(event.target.value)}
              placeholder="acme.com, acme.io"
              className={INPUT_CLASS}
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-xs text-muted-foreground">
              Role for new members
            </span>
            <select
              aria-label="Default role"
              value={defaultRole}
              onChange={(event) => setDefaultRole(event.target.value)}
              className={INPUT_CLASS}
            >
              <option value="member">Member</option>
              <option value="admin">Admin</option>
            </select>
          </label>
        </div>

        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            aria-label="Enable SSO"
            checked={enabled}
            onChange={(event) => setEnabled(event.target.checked)}
          />
          <span>Enable SSO for this workspace</span>
        </label>

        <div className="flex items-center gap-2">
          <Button type="submit" disabled={pending !== null}>
            {pending === "save" ? "Saving…" : "Save SSO settings"}
          </Button>
          {config.configured ? (
            <Button
              type="button"
              variant="ghost"
              disabled={pending !== null}
              onClick={disable}
            >
              {pending === "disable" ? "…" : "Remove config"}
            </Button>
          ) : null}
        </div>
      </form>
    </div>
  )
}
