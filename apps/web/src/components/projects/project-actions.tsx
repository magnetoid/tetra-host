"use client"

import { useRouter } from "next/navigation"
import { useState } from "react"

import { AlertBanner } from "@/components/ui/alert-banner"

export function ProjectActions({ applicationId }: { applicationId: string }) {
  const router = useRouter()
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pendingAction, setPendingAction] = useState<string | null>(null)

  async function runAction(action: "deploy" | "start" | "restart") {
    setPendingAction(action)
    setMessage(null)
    setError(null)

    try {
      const response = await fetch(`/api/proxy/projects/${applicationId}/${action}`, {
        method: "POST",
      })
      const payload = (await response.json()) as { message?: string; detail?: string; error?: string }

      if (!response.ok) {
        setError(payload.detail ?? payload.error ?? "Action failed.")
        return
      }

      setMessage(payload.message ?? "Action queued.")
      router.refresh()
    } catch {
      setError("Unable to reach the control plane.")
    } finally {
      setPendingAction(null)
    }
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
            disabled={pendingAction !== null}
            onClick={() => runAction(action)}
            className="rounded-lg border border-border px-3 py-2 text-sm text-zinc-200 transition hover:bg-zinc-900 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {pendingAction === action
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
