"use client"

import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import { useState } from "react"

import { AlertBanner } from "@/components/ui/alert-banner"
import { Button } from "@/components/ui/button"
import { useAction } from "@/hooks/use-action"
import { apiFetch } from "@/lib/client-api"
import { faPlus, faTrash } from "@/lib/icons"
import type { AppStorageRecord } from "@/lib/types"

const inputClass =
  "w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/25"

/**
 * Persistent storage volumes for an app — data mounted here survives redeploys
 * (uploads, databases-in-container, caches). Coolify-backed.
 */
export function AppVolumes({ appId, volumes }: { appId: string; volumes: AppStorageRecord[] }) {
  const { run, pending, error } = useAction()
  const [name, setName] = useState("")
  const [mountPath, setMountPath] = useState("")

  async function add(event: React.FormEvent) {
    event.preventDefault()
    const ok = await run(
      () =>
        apiFetch(`/api/proxy/projects/${appId}/storages`, {
          method: "POST",
          body: { name: name.trim(), mount_path: mountPath.trim() },
          errorMessage: "Couldn't add volume.",
        }),
      { key: "add", successMessage: "Volume added" },
    )
    if (ok) {
      setName("")
      setMountPath("")
    }
  }

  function remove(vol: AppStorageRecord) {
    if (!window.confirm(`Remove volume ${vol.mount_path || vol.name}? Its data will be lost.`)) return
    return run(
      () =>
        apiFetch(`/api/proxy/projects/${appId}/storages/${vol.id}`, {
          method: "DELETE",
          errorMessage: "Couldn't remove volume.",
        }),
      { key: vol.id, successMessage: "Volume removed" },
    )
  }

  return (
    <div className="space-y-4">
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}

      <div className="space-y-2">
        {volumes.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No volumes yet. Without one, container data is wiped on every redeploy.
          </p>
        ) : (
          volumes.map((vol) => (
            <div
              key={vol.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-background p-3"
            >
              <div className="min-w-0 font-mono text-sm">
                <span className="text-foreground">{vol.mount_path || "—"}</span>
                {vol.name ? <span className="ml-2 text-xs text-muted-foreground">{vol.name}</span> : null}
              </div>
              <button
                type="button"
                onClick={() => remove(vol)}
                disabled={pending !== null}
                className="rounded-lg border border-border p-2 text-muted-foreground transition-colors hover:border-status-err/40 hover:text-status-err disabled:opacity-50"
                aria-label={`Remove ${vol.mount_path || vol.name}`}
              >
                <FontAwesomeIcon icon={faTrash} className="h-3.5 w-3.5" />
              </button>
            </div>
          ))
        )}
      </div>

      <form onSubmit={add} className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
        <input
          value={mountPath}
          onChange={(e) => setMountPath(e.target.value)}
          placeholder="/app/data (mount path)"
          aria-label="Mount path"
          className={`${inputClass} font-mono`}
        />
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="volume name (optional)"
          aria-label="Volume name"
          className={inputClass}
        />
        <Button type="submit" icon={faPlus} disabled={pending !== null || !mountPath.trim()}>
          {pending === "add" ? "Adding…" : "Add volume"}
        </Button>
      </form>
      <p className="text-xs text-muted-foreground">Redeploy after adding for the mount to take effect.</p>
    </div>
  )
}
