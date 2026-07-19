"use client"

import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import { useState } from "react"

import { AlertBanner } from "@/components/ui/alert-banner"
import { Button } from "@/components/ui/button"
import { useAction } from "@/hooks/use-action"
import { apiFetch } from "@/lib/client-api"
import { faBell, faPaperPlane, faPlus, faTrash } from "@/lib/icons"
import type {
  NotificationChannelCreated,
  NotificationChannelSummary,
  NotificationTestResult,
} from "@/lib/types"

const INPUT_CLASS =
  "rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/25"

/**
 * Outbound webhook notification channels (parity with `tetra notifications …`).
 * The platform POSTs signed deploy-event payloads to each URL. The signing secret
 * is revealed once at creation. Mirrors the API-tokens manager pattern.
 */
export function NotificationsManager({ channels }: { channels: NotificationChannelSummary[] }) {
  const { run, pending, error } = useAction()
  const [name, setName] = useState("")
  const [url, setUrl] = useState("")
  const [created, setCreated] = useState<NotificationChannelCreated | null>(null)
  const [testResult, setTestResult] = useState<{ id: string; ok: boolean; status: string } | null>(null)

  async function createChannel(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    await run(
      async () => {
        const payload = await apiFetch<NotificationChannelCreated>("/api/proxy/account/notifications", {
          method: "POST",
          body: { name, url, events: "*" },
          errorMessage: "Could not create channel.",
        })
        setCreated(payload)
        setName("")
        setUrl("")
      },
      { key: "create" },
    )
  }

  function testChannel(id: string) {
    return run(
      async () => {
        const result = await apiFetch<NotificationTestResult>(
          `/api/proxy/account/notifications/${id}/test`,
          { method: "POST", errorMessage: "Could not send test." },
        )
        setTestResult({ id, ok: result.ok, status: result.status })
      },
      { key: `test:${id}` },
    )
  }

  function deleteChannel(id: string) {
    return run(
      async () => {
        await apiFetch(`/api/proxy/account/notifications/${id}`, {
          method: "DELETE",
          errorMessage: "Could not delete channel.",
        })
        if (created?.id === id) setCreated(null)
        if (testResult?.id === id) setTestResult(null)
      },
      { key: `rm:${id}`, successMessage: "Channel deleted" },
    )
  }

  return (
    <div className="space-y-4">
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}

      <form
        onSubmit={createChannel}
        className="flex flex-wrap items-end gap-3 rounded-lg border border-border bg-muted p-4"
      >
        <label className="block text-sm">
          <span className="mb-2 block text-muted-foreground">Name</span>
          <input
            aria-label="Channel name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="team-slack"
            className={`${INPUT_CLASS} w-40`}
            required
          />
        </label>
        <label className="block flex-1 text-sm">
          <span className="mb-2 block text-muted-foreground">Webhook URL</span>
          <input
            aria-label="Webhook URL"
            type="url"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://hooks.slack.com/services/…"
            className={`${INPUT_CLASS} w-full`}
            required
          />
        </label>
        <Button type="submit" icon={faPlus} disabled={pending !== null}>
          {pending === "create" ? "…" : "Add channel"}
        </Button>
      </form>

      {created ? (
        <div className="rounded-lg border border-status-ok/25 bg-status-ok/10 p-4 text-sm">
          <div className="font-medium text-status-ok">
            Channel created. Save the signing secret — it is shown only once.
          </div>
          <div className="mt-3 break-all rounded-md border border-border bg-background p-3 font-mono text-xs">
            {created.secret}
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            Deliveries are signed{" "}
            <span className="font-mono">X-Tetra-Signature: sha256=HMAC(secret, body)</span> — verify
            it on your receiver to confirm authenticity.
          </p>
        </div>
      ) : null}

      {channels.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No channels yet. Add a webhook URL (Slack, Discord, or your own endpoint) to receive signed
          events when your deploys succeed or fail.
        </p>
      ) : (
        <div className="space-y-2">
          {channels.map((channel) => (
            <div
              key={channel.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-muted px-4 py-3"
            >
              <div className="flex min-w-0 items-center gap-3 text-sm">
                <FontAwesomeIcon icon={faBell} className="h-3.5 w-3.5 text-muted-foreground" />
                <span className="font-medium">{channel.name}</span>
                <span className="truncate font-mono text-xs text-muted-foreground">{channel.url}</span>
                {channel.last_status ? (
                  <span
                    className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                      channel.last_status === "ok"
                        ? "bg-status-ok/10 text-status-ok"
                        : "bg-status-warn/10 text-status-warn"
                    }`}
                  >
                    {channel.last_status}
                  </span>
                ) : null}
                {testResult?.id === channel.id ? (
                  <span
                    className={`text-xs ${testResult.ok ? "text-status-ok" : "text-status-warn"}`}
                  >
                    test: {testResult.status}
                  </span>
                ) : null}
              </div>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="secondary"
                  icon={faPaperPlane}
                  disabled={pending !== null}
                  onClick={() => testChannel(channel.id)}
                >
                  {pending === `test:${channel.id}` ? "…" : "Test"}
                </Button>
                <Button
                  size="sm"
                  variant="danger"
                  icon={faTrash}
                  disabled={pending !== null}
                  onClick={() => deleteChannel(channel.id)}
                >
                  {pending === `rm:${channel.id}` ? "…" : "Delete"}
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
