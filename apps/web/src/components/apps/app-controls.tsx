"use client"

import { AlertBanner } from "@/components/ui/alert-banner"
import { Button } from "@/components/ui/button"
import { useAction } from "@/hooks/use-action"
import { apiFetch } from "@/lib/client-api"
import { faArrowsRotate, faCirclePlay, faCircleStop } from "@/lib/icons"

type ControlAction = "start" | "stop" | "restart"

const ACTIONS: { action: ControlAction; label: string; done: string; icon: typeof faCirclePlay }[] = [
  { action: "restart", label: "Restart", done: "App restarted", icon: faArrowsRotate },
  { action: "stop", label: "Stop", done: "App stopped", icon: faCircleStop },
  { action: "start", label: "Start", done: "App started", icon: faCirclePlay },
]

/** Start, stop or restart an engine app's containers (same version, no rebuild). */
export function AppControls({ project }: { project: string }) {
  const { run, pending, error } = useAction()

  function control(action: ControlAction, done: string) {
    return run(
      () =>
        apiFetch(`/api/proxy/apps/${encodeURIComponent(project)}/${action}`, {
          method: "POST",
          errorMessage: `Could not ${action} the app.`,
        }),
      { key: action, successMessage: done },
    )
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
            onClick={() => control(action, done)}
          >
            {pending === action ? "…" : label}
          </Button>
        ))}
      </div>
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}
    </div>
  )
}
