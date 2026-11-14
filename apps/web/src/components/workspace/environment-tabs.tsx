"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { useState } from "react"

import { AlertBanner } from "@/components/ui/alert-banner"
import { Button } from "@/components/ui/button"
import { useAction } from "@/hooks/use-action"
import { apiFetch } from "@/lib/client-api"
import { faPlus } from "@/lib/icons"
import { projectHref } from "@/lib/navigation"
import type { EnvironmentKind, WorkspaceEnvironment } from "@/lib/types"
import { cn } from "@/lib/utils"

const INPUT =
  "rounded-xl border border-border bg-background px-3 py-2 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/25"

/** One tab per environment of the project, plus an inline "add environment" form. */
export function EnvironmentTabs({
  team,
  project,
  environments,
  current,
}: {
  team: string
  project: string
  environments: WorkspaceEnvironment[]
  current: string
}) {
  const router = useRouter()
  const { run, pending, error } = useAction()
  const [adding, setAdding] = useState(false)
  const [name, setName] = useState("Staging")
  const [kind, setKind] = useState<EnvironmentKind>("staging")

  async function create(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    let slug = ""
    const ok = await run(
      async () => {
        const env = await apiFetch<WorkspaceEnvironment>(
          `/api/proxy/teams/${team}/projects/${encodeURIComponent(project)}/environments`,
          { method: "POST", body: { name: name.trim(), kind }, errorMessage: "Could not add the environment." },
        )
        slug = env.slug
      },
      { key: "env", successMessage: `${name.trim()} added`, refresh: false },
    )
    if (ok && slug) {
      setAdding(false)
      router.push(projectHref(project, slug))
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-1 border-b border-border" role="tablist" aria-label="Environments">
        {environments.map((env) => {
          const active = env.slug === current
          return (
            <Link
              key={env.id}
              href={projectHref(project, env.slug)}
              role="tab"
              aria-selected={active}
              className={cn(
                "-mb-px border-b-2 px-3 py-2 text-sm transition-colors",
                active
                  ? "border-primary font-medium text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground",
              )}
            >
              {env.name}
              <span className="ml-1.5 text-xs text-muted-foreground">{env.apps}</span>
            </Link>
          )
        })}
        <button
          type="button"
          onClick={() => setAdding((v) => !v)}
          className="-mb-px border-b-2 border-transparent px-3 py-2 text-sm text-muted-foreground hover:text-foreground"
        >
          + Environment
        </button>
      </div>
      {adding ? (
        <form onSubmit={create} className="flex flex-wrap items-end gap-3">
          <label className="block text-sm">
            <span className="mb-1.5 block text-muted-foreground">Name</span>
            <input aria-label="Environment name" value={name} onChange={(e) => setName(e.target.value)} className={INPUT} required />
          </label>
          <label className="block text-sm">
            <span className="mb-1.5 block text-muted-foreground">Kind</span>
            <select aria-label="Environment kind" value={kind} onChange={(e) => setKind(e.target.value as EnvironmentKind)} className={INPUT}>
              <option value="staging">Staging</option>
              <option value="production">Production</option>
              <option value="preview">Preview</option>
            </select>
          </label>
          <Button type="submit" size="sm" icon={faPlus} disabled={pending !== null || !name.trim()}>
            {pending === "env" ? "Adding…" : "Add environment"}
          </Button>
        </form>
      ) : null}
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}
    </div>
  )
}
