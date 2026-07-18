"use client"

import { useCallback, useEffect, useState } from "react"

import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { AlertBanner } from "@/components/ui/alert-banner"
import { useAction } from "@/hooks/use-action"
import { apiFetch } from "@/lib/client-api"
import { faArrowUpRightFromSquare, faKey, faPlus, faTrash, faXmark } from "@/lib/icons"
import type { MailAppPassword, MailAppPasswordCreateResult, MailboxRecord } from "@/lib/types"

const inputClass =
  "rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none transition focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/40"

/**
 * Per-mailbox management: edit (quota, display name, active, reset password) and
 * app passwords (purpose-scoped IMAP/SMTP credentials). App passwords are fetched
 * client-side; the generated secret is shown exactly once (mailcow never echoes it).
 */
export function MailboxPanel({
  mailbox,
  webmailBase = "",
  onClose,
}: {
  mailbox: MailboxRecord
  /** Panel public origin; when set, an "Open webmail" (OIDC SSO) button appears. */
  webmailBase?: string
  onClose: () => void
}) {
  const enc = encodeURIComponent(mailbox.username)
  const webmailHref = webmailBase
    ? `${webmailBase.replace(/\/$/, "")}/oidc/launch?mailbox=${enc}`
    : ""

  return (
    <section className="rounded-lg border border-primary/30 bg-card p-6 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Manage mailbox</h2>
          <p className="mt-0.5 font-mono text-sm text-muted-foreground">{mailbox.username}</p>
        </div>
        <div className="flex items-center gap-2">
          {webmailHref ? (
            <a
              href={webmailHref}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-lg border border-primary/40 bg-primary/5 px-2.5 py-2 text-xs font-medium text-primary transition-colors hover:bg-primary/10"
            >
              <FontAwesomeIcon icon={faArrowUpRightFromSquare} className="h-3.5 w-3.5" />
              Open webmail
            </a>
          ) : null}
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-border p-2 text-muted-foreground transition-colors hover:text-foreground"
            aria-label="Close mailbox management"
          >
            <FontAwesomeIcon icon={faXmark} className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      <div className="mt-6 grid gap-8 lg:grid-cols-2">
        <EditMailbox mailbox={mailbox} enc={enc} />
        <AppPasswords enc={enc} />
      </div>
    </section>
  )
}

function EditMailbox({ mailbox, enc }: { mailbox: MailboxRecord; enc: string }) {
  const { run, pending, error } = useAction()
  const [name, setName] = useState(mailbox.name)
  const [quotaMb, setQuotaMb] = useState(String(Math.round(mailbox.quota_bytes / (1024 * 1024))))
  const [active, setActive] = useState(mailbox.active)
  const [password, setPassword] = useState("")

  async function save(event: React.FormEvent) {
    event.preventDefault()
    const body: Record<string, unknown> = {}
    if (name.trim() !== mailbox.name) body.name = name.trim()
    const quota = Number(quotaMb)
    if (Number.isFinite(quota) && quota > 0 && quota !== Math.round(mailbox.quota_bytes / (1024 * 1024))) {
      body.quota_mb = quota
    }
    if (active !== mailbox.active) body.active = active
    if (password) body.password = password
    if (Object.keys(body).length === 0) return

    const ok = await run(
      () =>
        apiFetch(`/api/proxy/mail/mailboxes/${enc}`, {
          method: "PATCH",
          body,
          errorMessage: "Could not update mailbox.",
        }),
      { key: "edit", successMessage: "Mailbox updated" },
    )
    if (ok) setPassword("")
  }

  return (
    <form onSubmit={save} className="space-y-4">
      <h3 className="text-sm font-semibold text-foreground">Settings</h3>
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}

      <label className="block space-y-1.5">
        <span className="text-xs font-medium text-muted-foreground">Display name</span>
        <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Display name" />
      </label>

      <label className="block space-y-1.5">
        <span className="text-xs font-medium text-muted-foreground">Quota (MB)</span>
        <Input
          type="number"
          min={1}
          value={quotaMb}
          onChange={(e) => setQuotaMb(e.target.value)}
          placeholder="3072"
        />
      </label>

      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={active}
          onChange={(e) => setActive(e.target.checked)}
          className="size-4 rounded border-border"
        />
        <span>Active (can send &amp; receive)</span>
      </label>

      <label className="block space-y-1.5">
        <span className="text-xs font-medium text-muted-foreground">Reset password</span>
        <Input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Leave blank to keep current"
          autoComplete="new-password"
        />
        <span className="text-xs text-muted-foreground">Min 8 characters. Blank = unchanged.</span>
      </label>

      <Button type="submit" disabled={pending !== null || (!!password && password.length < 8)}>
        {pending === "edit" ? "Saving…" : "Save changes"}
      </Button>
    </form>
  )
}

function AppPasswords({ enc }: { enc: string }) {
  const { run, pending, error } = useAction()
  const [items, setItems] = useState<MailAppPassword[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [appName, setAppName] = useState("")
  const [revealed, setRevealed] = useState<MailAppPasswordCreateResult | null>(null)

  // Pure fetch (no setState) so the mount effect can drive it through promise
  // callbacks — matching the console's fetch-on-mount convention and keeping
  // setState out of the synchronous effect body.
  const fetchList = useCallback(
    () =>
      apiFetch<MailAppPassword[]>(`/api/proxy/mail/mailboxes/${enc}/app-passwords`, {
        errorMessage: "Could not load app passwords.",
      }),
    [enc],
  )

  useEffect(() => {
    let cancelled = false
    fetchList()
      .then((data) => {
        if (!cancelled) {
          setItems(data)
          setLoadError(null)
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setLoadError(err instanceof Error ? err.message : "Could not load app passwords.")
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [fetchList])

  // Post-mutation reload — runs from event handlers, where setState is fine.
  const reload = useCallback(async () => {
    try {
      setItems(await fetchList())
      setLoadError(null)
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Could not load app passwords.")
    }
  }, [fetchList])

  async function create(event: React.FormEvent) {
    event.preventDefault()
    setRevealed(null)
    await run(
      async () => {
        const result = await apiFetch<MailAppPasswordCreateResult>(
          `/api/proxy/mail/mailboxes/${enc}/app-passwords`,
          {
            method: "POST",
            body: { app_name: appName.trim() || "App password" },
            errorMessage: "Could not create app password.",
          },
        )
        setRevealed(result)
        setAppName("")
        await reload()
      },
      { key: "create", refresh: false, successMessage: "App password created" },
    )
  }

  async function remove(id: number, name: string) {
    if (!window.confirm(`Delete app password "${name}"? Apps using it will stop connecting.`)) return
    await run(
      async () => {
        await apiFetch(`/api/proxy/mail/mailboxes/${enc}/app-passwords/${id}`, {
          method: "DELETE",
          errorMessage: "Could not delete app password.",
        })
        await reload()
      },
      { key: `del-${id}`, refresh: false, successMessage: "App password deleted" },
    )
  }

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-semibold text-foreground">App passwords</h3>
        <p className="mt-0.5 text-xs text-muted-foreground">
          Purpose-scoped IMAP/SMTP credentials — hand these to mail clients instead of the mailbox
          password. Revoke one anytime without changing the main password.
        </p>
      </div>

      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}
      {loadError ? <AlertBanner tone="error">{loadError}</AlertBanner> : null}

      {revealed ? (
        <div className="rounded-lg border border-primary/40 bg-primary/5 p-3">
          <div className="text-xs font-medium text-foreground">
            “{revealed.app_name}” — copy it now, it won’t be shown again:
          </div>
          <div className="mt-1 select-all font-mono text-sm text-primary">{revealed.password}</div>
        </div>
      ) : null}

      <form onSubmit={create} className="flex gap-2">
        <input
          value={appName}
          onChange={(e) => setAppName(e.target.value)}
          placeholder="e.g. Thunderbird, iPhone"
          aria-label="App password name"
          className={`flex-1 ${inputClass}`}
        />
        <Button type="submit" icon={faPlus} disabled={pending !== null}>
          {pending === "create" ? "Creating…" : "Create"}
        </Button>
      </form>

      <div className="space-y-2">
        {loading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : items.length === 0 ? (
          <p className="text-sm text-muted-foreground">No app passwords yet.</p>
        ) : (
          items.map((item) => (
            <div
              key={item.id}
              className="flex items-center justify-between gap-3 rounded-lg border border-border bg-background px-3 py-2"
            >
              <span className="flex items-center gap-2 text-sm">
                <FontAwesomeIcon icon={faKey} className="h-3.5 w-3.5 text-muted-foreground" />
                {item.name || `App password ${item.id}`}
              </span>
              <button
                type="button"
                onClick={() => remove(item.id, item.name)}
                disabled={pending !== null}
                className="rounded-lg border border-border p-1.5 text-muted-foreground transition-colors hover:border-status-err/40 hover:text-status-err disabled:opacity-50"
                aria-label={`Delete app password ${item.name}`}
              >
                <FontAwesomeIcon icon={faTrash} className="h-3 w-3" />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
