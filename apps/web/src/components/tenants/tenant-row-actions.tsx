"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"

import { Button } from "@/components/ui/button"
import { faBan, faCircleCheck, faCirclePlay, faCircleStop } from "@/lib/icons"
import type { TenantRecord } from "@/lib/types"

type Action = "approve" | "reject" | "suspend" | "reactivate"

export function TenantRowActions({ tenant }: { tenant: TenantRecord }) {
  const router = useRouter()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const status = tenant.status ?? "active"

  async function doAction(action: Action) {
    setBusy(true)
    setError(null)
    try {
      const res = await fetch(`/api/proxy/tenants/${tenant.slug}/${action}`, {
        method: "POST",
      })
      if (!res.ok) {
        let detail = res.statusText
        try {
          const payload = (await res.json()) as { detail?: string }
          if (payload.detail) detail = payload.detail
        } catch {
          // keep statusText
        }
        setError(detail)
        return
      }
      router.refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error")
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-wrap items-center justify-end gap-2">
      {error ? <span className="text-xs text-red-400">{error}</span> : null}

      {/* pending → approve or reject */}
      {status === "pending" && (
        <>
          <Button
            aria-label={`Approve ${tenant.name}`}
            size="sm"
            variant="primary"
            icon={faCircleCheck}
            disabled={busy}
            onClick={() => doAction("approve")}
          >
            Approve
          </Button>
          <Button
            aria-label={`Reject ${tenant.name}`}
            size="sm"
            variant="danger"
            icon={faBan}
            disabled={busy}
            onClick={() => doAction("reject")}
          >
            Reject
          </Button>
        </>
      )}

      {/* active → suspend */}
      {status === "active" && (
        <Button
          aria-label={`Suspend ${tenant.name}`}
          size="sm"
          variant="danger"
          icon={faCircleStop}
          disabled={busy}
          onClick={() => doAction("suspend")}
        >
          Suspend
        </Button>
      )}

      {/* suspended or rejected → reactivate */}
      {(status === "suspended" || status === "rejected") && (
        <Button
          aria-label={`Reactivate ${tenant.name}`}
          size="sm"
          variant="secondary"
          icon={faCirclePlay}
          disabled={busy}
          onClick={() => doAction("reactivate")}
        >
          Reactivate
        </Button>
      )}
    </div>
  )
}
