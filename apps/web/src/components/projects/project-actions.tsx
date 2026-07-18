"use client"

import { useState } from "react"

import { AlertBanner } from "@/components/ui/alert-banner"
import { useAction } from "@/hooks/use-action"
import { apiFetch } from "@/lib/client-api"

export function ProjectActions({ applicationId }: { applicationId: string }) {
  const { run, pending, error } = useAction()
  const [message, setMessage] = useState<string | null>(null)

  async function runAction(action: "deploy" | "start" | "restart") {
    setMessage(null)
    await run(
      async () => {
        const payload = await apiFetch<{ message?: string }>(
          `/api/proxy/projects/${applicationId}/${action}`,
          { method: "POST", errorMessage: "Action failed." },
        )
        setMessage(payload.message ?? "Action queued.")
      },
      { key: action },
    )
  }

  return (
    <div className="space-y-3">
      {message ? <AlertBanner tone="success">{message}</AlertBanner> : null}
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}
      <div className="flex flex-wrap gap-2">
        {(["deploy", "start", "restart"] as const).map((action) => (
          <button
            key={action}
            type="button"
            disabled={pending !== null}
            onClick={() => runAction(action)}
            className="rounded-lg border border-border px-3 py-2 text-sm text-foreground transition-colors hover:bg-accent disabled:cursor-not-allowed disabled:opacity-60"
          >
            {pending === action
              ? "Working..."
              : action === "deploy"
                ? "Trigger deploy"
                : action[0].toUpperCase() + action.slice(1)}
          </button>
        ))}
      </div>
    </div>
  )
}
