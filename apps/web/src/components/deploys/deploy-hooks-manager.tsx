"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"

import { AlertBanner } from "@/components/ui/alert-banner"
import { Button } from "@/components/ui/button"
import { faGithub, faPlus, faTrash } from "@/lib/icons"
import type { DeployHook, DeployHookCreated } from "@/lib/types"

const INPUT_CLASS =
  "rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/25"

export function DeployHooksManager({ hooks }: { hooks: DeployHook[] }) {
  const router = useRouter()
  const [project, setProject] = useState("")
  const [gitUrl, setGitUrl] = useState("")
  const [ref, setRef] = useState("main")
  const [created, setCreated] = useState<DeployHookCreated | null>(null)
  const [pending, setPending] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function createHook(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setPending("create")
    setError(null)
    try {
      const response = await fetch("/api/proxy/deploy-hooks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project, git_url: gitUrl, ref }),
      })
      const payload = (await response.json().catch(() => ({}))) as DeployHookCreated & {
        detail?: string
      }
      if (!response.ok) {
        setError(payload.detail ?? "Could not create webhook.")
        return
      }
      setCreated(payload)
      setProject("")
      setGitUrl("")
      router.refresh()
    } catch {
      setError("Unable to reach the control plane.")
    } finally {
      setPending(null)
    }
  }

  async function removeHook(hookId: string) {
    setPending(`rm:${hookId}`)
    setError(null)
    try {
      const response = await fetch(`/api/proxy/deploy-hooks/${hookId}`, { method: "DELETE" })
      if (!response.ok) {
        const payload = (await response.json().catch(() => ({}))) as { detail?: string }
        setError(payload.detail ?? "Could not remove webhook.")
        return
      }
      if (created?.id === hookId) setCreated(null)
      router.refresh()
    } catch {
      setError("Unable to reach the control plane.")
    } finally {
      setPending(null)
    }
  }

  return (
    <div className="space-y-4">
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}

      <form
        onSubmit={createHook}
        className="flex flex-wrap items-end gap-3 rounded-2xl border border-border bg-muted p-4"
      >
        <label className="block text-sm">
          <span className="mb-2 block text-zinc-400">App</span>
          <input
            aria-label="Webhook app"
            value={project}
            onChange={(event) => setProject(event.target.value)}
            placeholder="my-app"
            className={INPUT_CLASS}
            required
          />
        </label>
        <label className="block flex-1 text-sm">
          <span className="mb-2 block text-zinc-400">Git repository</span>
          <input
            aria-label="Webhook git repository"
            value={gitUrl}
            onChange={(event) => setGitUrl(event.target.value)}
            placeholder="https://github.com/you/app"
            className={`${INPUT_CLASS} w-full`}
            required
          />
        </label>
        <label className="block text-sm">
          <span className="mb-2 block text-zinc-400">Branch</span>
          <input
            aria-label="Webhook branch"
            value={ref}
            onChange={(event) => setRef(event.target.value)}
            className={`${INPUT_CLASS} w-28`}
          />
        </label>
        <Button type="submit" icon={faPlus} disabled={pending !== null}>
          {pending === "create" ? "…" : "Create webhook"}
        </Button>
      </form>

      {created ? (
        <div className="rounded-2xl border border-emerald-900 bg-emerald-950/40 p-4 text-sm">
          <div className="font-medium text-emerald-300">
            Webhook created — add it to GitHub now. The secret is shown only once.
          </div>
          <div className="mt-3 space-y-1 font-mono text-xs text-zinc-300">
            <div>
              <span className="text-zinc-500">Payload URL:&nbsp;</span>
              {created.url}
            </div>
            <div>
              <span className="text-zinc-500">Secret:&nbsp;</span>
              {created.secret}
            </div>
            <div className="text-zinc-500">Content type: application/json · Events: push</div>
          </div>
        </div>
      ) : null}

      {hooks.length === 0 ? (
        <p className="text-sm text-zinc-500">
          No push-to-deploy webhooks yet — create one and a <span className="font-mono">git push</span> will
          redeploy the app.
        </p>
      ) : (
        <div className="space-y-2">
          {hooks.map((hook) => (
            <div
              key={hook.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-border bg-muted px-4 py-3"
            >
              <div className="flex min-w-0 items-center gap-3 text-sm">
                <span className="font-medium">{hook.project}</span>
                <span className="font-mono text-xs text-zinc-500">@{hook.ref}</span>
                <span className="truncate font-mono text-xs text-zinc-600">{hook.git_url}</span>
              </div>
              <Button
                size="sm"
                variant="danger"
                icon={faTrash}
                disabled={pending !== null}
                onClick={() => removeHook(hook.id)}
              >
                {pending === `rm:${hook.id}` ? "…" : "Remove"}
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
