"use client"

import { useRouter } from "next/navigation"
import { useState } from "react"

import { useScopeLabels } from "@/components/shell/scope-labels"
import { AlertBanner } from "@/components/ui/alert-banner"
import { Button } from "@/components/ui/button"
import { Modal } from "@/components/ui/modal"
import { useAction } from "@/hooks/use-action"
import { apiFetch } from "@/lib/client-api"
import { faArrowsRotate, faCirclePlay, faCircleStop, faTrash } from "@/lib/icons"
import { projectHref } from "@/lib/navigation"
import type { DatabaseRecord } from "@/lib/types"

const ACTIONS = [
  { action: "restart", label: "Restart", done: "Database restarted", icon: faArrowsRotate },
  { action: "stop", label: "Stop", done: "Database stopped", icon: faCircleStop },
  { action: "start", label: "Start", done: "Database started", icon: faCirclePlay },
] as const

/** Start/stop/restart a database, and delete it behind a type-the-name confirmation. */
export function DatabaseControls({ database }: { database: DatabaseRecord }) {
  const router = useRouter()
  const labels = useScopeLabels()
  const { run, pending, error } = useAction()
  const [confirming, setConfirming] = useState(false)
  const [typed, setTyped] = useState("")
  const base = `/api/proxy/databases/${encodeURIComponent(database.id)}`

  async function remove() {
    const ok = await run(
      () => apiFetch(base, { method: "DELETE", errorMessage: "Could not delete the database." }),
      { key: "delete", successMessage: `${database.name} deleted`, refresh: false },
    )
    // Back to the environment it lived in, when the page knows it.
    if (ok) {
      router.push(
        labels.projectSlug && labels.environmentSlug
          ? projectHref(labels.projectSlug, labels.environmentSlug)
          : "/projects",
      )
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        {ACTIONS.map(({ action, label, done, icon }) => (
          <Button
            key={action}
            size="sm"
            icon={icon}
            disabled={pending !== null}
            onClick={() =>
              run(
                () =>
                  apiFetch(`${base}/${action}`, {
                    method: "POST",
                    errorMessage: `Could not ${action} the database.`,
                  }),
                { key: action, successMessage: done },
              )
            }
          >
            {pending === action ? "…" : label}
          </Button>
        ))}
        <Button
          size="sm"
          variant="danger"
          icon={faTrash}
          disabled={pending !== null}
          onClick={() => {
            setTyped("")
            setConfirming(true)
          }}
        >
          Delete
        </Button>
      </div>
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}
      <Modal
        open={confirming}
        onOpenChange={setConfirming}
        title={`Delete ${database.name}?`}
        description="This removes the database, its data volume and every backup. It can't be undone."
        footer={
          <div className="flex justify-end gap-2">
            <Button onClick={() => setConfirming(false)}>Cancel</Button>
            <Button
              variant="destructive"
              disabled={typed !== database.name || pending !== null}
              onClick={remove}
            >
              {pending === "delete" ? "Deleting…" : "Delete database"}
            </Button>
          </div>
        }
      >
        <label className="block text-sm">
          <span className="mb-2 block text-muted-foreground">
            Type <span className="font-mono text-foreground">{database.name}</span> to confirm
          </span>
          <input
            aria-label="Database name"
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            className="w-full rounded-xl border border-border bg-background px-3 py-2.5 font-mono text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/25"
            autoComplete="off"
          />
        </label>
      </Modal>
    </div>
  )
}
