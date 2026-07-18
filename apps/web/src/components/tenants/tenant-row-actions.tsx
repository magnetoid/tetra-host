"use client"

import { Button } from "@/components/ui/button"
import { useAction } from "@/hooks/use-action"
import { apiFetch } from "@/lib/client-api"
import { faBan, faCircleCheck, faCirclePlay, faCircleStop } from "@/lib/icons"
import type { TenantRecord } from "@/lib/types"

type Action = "approve" | "reject" | "suspend" | "reactivate"

const ACTION_DONE: Record<Action, string> = {
  approve: "Tenant approved",
  reject: "Tenant rejected",
  suspend: "Tenant suspended",
  reactivate: "Tenant reactivated",
}

export function TenantRowActions({ tenant }: { tenant: TenantRecord }) {
  const { run, pending, error } = useAction()
  const busy = pending !== null
  const status = tenant.status ?? "active"

  function doAction(action: Action) {
    return run(
      () =>
        apiFetch(`/api/proxy/tenants/${tenant.slug}/${action}`, {
          method: "POST",
          errorMessage: "Action failed.",
        }),
      { key: action, successMessage: ACTION_DONE[action] },
    )
  }

  return (
    <div className="flex flex-wrap items-center justify-end gap-2">
      {error ? <span className="text-xs text-status-err">{error}</span> : null}

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
