"use client"

import { useState } from "react"

import { AlertBanner } from "@/components/ui/alert-banner"
import { useAction } from "@/hooks/use-action"
import { apiFetch } from "@/lib/client-api"
import type { ZoneSettings } from "@/lib/types"

const SSL_MODES = ["off", "flexible", "full", "strict"]
const SECURITY_LEVELS = ["off", "essentially_off", "low", "medium", "high", "under_attack"]

const selectClass =
  "rounded-lg border border-border bg-background px-3 py-1.5 text-sm text-foreground focus:border-primary focus:outline-none disabled:opacity-60"

export function ZoneTools({ zoneId, settings }: { zoneId: string; settings: ZoneSettings }) {
  const { run, pending, error } = useAction()
  const [message, setMessage] = useState<string | null>(null)

  async function call(path: string, body: unknown, label: string, method: "PATCH" | "POST" = "PATCH") {
    setMessage(null)
    await run(
      async () => {
        const payload = await apiFetch<{ message?: string }>(
          `/api/proxy/dns/zones/${zoneId}/${path}`,
          { method, body, errorMessage: "Update failed." },
        )
        setMessage(payload.message ?? "Updated.")
      },
      { key: label },
    )
  }

  const setSetting = (setting: string, value: string) => call("settings", { setting, value }, setting)

  return (
    <div className="space-y-4 rounded-lg border border-border bg-muted p-6">
      <h2 className="text-lg font-semibold">Zone tools</h2>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="SSL/TLS mode">
          <select
            disabled={pending !== null}
            value={settings.ssl}
            onChange={(event) => setSetting("ssl", event.target.value)}
            className={selectClass}
          >
            {SSL_MODES.map((mode) => (
              <option key={mode} value={mode}>
                {mode}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Security level">
          <select
            disabled={pending !== null}
            value={settings.security_level}
            onChange={(event) => setSetting("security_level", event.target.value)}
            className={selectClass}
          >
            {SECURITY_LEVELS.map((level) => (
              <option key={level} value={level}>
                {level.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        </Field>
        <Toggle
          label="Always use HTTPS"
          checked={settings.always_use_https === "on"}
          disabled={pending !== null}
          onChange={(checked) => setSetting("always_use_https", checked ? "on" : "off")}
        />
        <Toggle
          label="Development mode"
          checked={settings.development_mode === "on"}
          disabled={pending !== null}
          onChange={(checked) => setSetting("development_mode", checked ? "on" : "off")}
        />
        <Toggle
          label="DNSSEC"
          checked={settings.dnssec === "active"}
          disabled={pending !== null}
          onChange={(checked) => call("dnssec", { status: checked ? "active" : "disabled" }, "dnssec")}
        />
        <Field label="Cache">
          <button
            type="button"
            disabled={pending !== null}
            onClick={() => call("purge", { everything: true }, "purge", "POST")}
            className="rounded-lg border border-border px-3 py-1.5 text-sm text-foreground transition-colors hover:bg-accent disabled:opacity-60"
          >
            {pending === "purge" ? "Purging…" : "Purge everything"}
          </button>
        </Field>
      </div>
      {message ? <AlertBanner tone="success">{message}</AlertBanner> : null}
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5 text-sm text-muted-foreground">
      {label}
      {children}
    </label>
  )
}

function Toggle({
  label,
  checked,
  disabled,
  onChange,
}: {
  label: string
  checked: boolean
  disabled?: boolean
  onChange: (checked: boolean) => void
}) {
  return (
    <label className="flex items-center justify-between gap-3 rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground">
      {label}
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
      />
    </label>
  )
}
