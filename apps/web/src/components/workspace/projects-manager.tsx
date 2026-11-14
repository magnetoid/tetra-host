"use client"

import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useState } from "react"

import { AlertBanner } from "@/components/ui/alert-banner"
import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/ui/empty-state"
import { useAction } from "@/hooks/use-action"
import { apiFetch } from "@/lib/client-api"
import { faFolder, faPlus } from "@/lib/icons"
import { projectHref } from "@/lib/navigation"
import type { WorkspaceProject } from "@/lib/types"

const INPUT =
  "rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/25"

function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? "" : "s"}`
}

/** The team's projects as cards, and a form to start a new one. */
export function ProjectsManager({ team, projects }: { team: string; projects: WorkspaceProject[] }) {
  const router = useRouter()
  const { run, pending, error } = useAction()
  const [name, setName] = useState("")

  async function create(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    let slug = ""
    const ok = await run(
      async () => {
        const project = await apiFetch<WorkspaceProject>(`/api/proxy/teams/${team}/projects`, {
          method: "POST",
          body: { name: name.trim() },
          errorMessage: "Could not create the project.",
        })
        slug = project.slug
      },
      { key: "create", successMessage: `Project ${name.trim()} created`, refresh: false },
    )
    if (ok && slug) router.push(projectHref(slug, "production"))
  }

  return (
    <div className="space-y-6">
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}
      <form
        onSubmit={create}
        className="flex flex-wrap items-end gap-3 rounded-lg border border-border bg-muted p-4"
      >
        <label className="block text-sm">
          <span className="mb-2 block text-muted-foreground">Project name</span>
          <input
            aria-label="Project name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="My shop"
            maxLength={120}
            className={`${INPUT} w-64`}
            required
          />
        </label>
        <Button type="submit" variant="primary" icon={faPlus} disabled={pending !== null || !name.trim()}>
          {pending === "create" ? "Creating…" : "New project"}
        </Button>
        <p className="w-full text-xs text-muted-foreground">
          A project groups the services of one product. It starts with a production environment;
          add staging when you need it.
        </p>
      </form>

      {projects.length === 0 ? (
        <EmptyState
          title="No projects yet"
          description="Create one above, then add services to it: a git repository, a template or a database."
        />
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {projects.map((project) => (
            <li key={project.id}>
              <Link
                href={projectHref(project.slug)}
                className="flex h-full items-start gap-3 rounded-lg border border-border bg-card p-4 transition-colors hover:border-primary/40 hover:bg-accent"
              >
                <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
                  <FontAwesomeIcon icon={faFolder} className="size-3.5" />
                </span>
                <span className="min-w-0">
                  <span className="block truncate font-medium">{project.name}</span>
                  <span className="mt-1 block text-xs text-muted-foreground">
                    {plural(project.apps, "service")} · {plural(project.environments, "environment")}
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
