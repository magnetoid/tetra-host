"use client"

import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import { useState } from "react"

import { AppMarketplace } from "@/components/apps/app-marketplace"
import { DatabaseCreateForm } from "@/components/databases/databases-manager"
import { GitDeployForm } from "@/components/deploys/deploys-manager"
import { Button } from "@/components/ui/button"
import { faDatabase, faGithub, faPlus, faStore, faXmark } from "@/lib/icons"
import type { AppTemplate, DatabaseEngine } from "@/lib/types"
import { cn } from "@/lib/utils"

export type ServiceChoice = "git" | "template" | "database"

const CHOICES: { key: ServiceChoice; label: string; description: string; icon: typeof faGithub }[] = [
  {
    key: "git",
    label: "Git repository",
    description: "Build and run a repo: its Dockerfile, or zero-config Nixpacks.",
    icon: faGithub,
  },
  {
    key: "template",
    label: "Template",
    description: "One-click apps such as WordPress, Ghost or n8n.",
    icon: faStore,
  },
  {
    key: "database",
    label: "Database",
    description: "PostgreSQL, MySQL, MariaDB or Redis on the private network.",
    icon: faDatabase,
  },
]

/** "+ New service": pick what to add, then fill in that form. Everything lands in `environmentId`. */
export function NewService({
  environmentId,
  environmentName,
  templates,
  installedProjects,
  engines,
  initialOpen = false,
}: {
  environmentId: string
  environmentName: string
  templates: AppTemplate[]
  installedProjects: string[]
  engines: DatabaseEngine[]
  initialOpen?: boolean
}) {
  const [open, setOpen] = useState(initialOpen)
  const [choice, setChoice] = useState<ServiceChoice | null>(null)

  if (!open) {
    return (
      <Button variant="primary" icon={faPlus} onClick={() => setOpen(true)}>
        New service
      </Button>
    )
  }

  return (
    <section aria-label="New service" className="space-y-4 rounded-lg border border-border bg-card p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold">New service</h2>
          <p className="text-sm text-muted-foreground">It will be created in {environmentName}.</p>
        </div>
        <Button
          size="sm"
          icon={faXmark}
          onClick={() => {
            setOpen(false)
            setChoice(null)
          }}
        >
          Close
        </Button>
      </div>

      <div className="grid gap-3 sm:grid-cols-3" role="radiogroup" aria-label="Service type">
        {CHOICES.map((c) => (
          <button
            key={c.key}
            type="button"
            role="radio"
            aria-checked={choice === c.key}
            onClick={() => setChoice(c.key)}
            className={cn(
              "flex items-start gap-3 rounded-lg border p-4 text-left transition-colors",
              choice === c.key
                ? "border-primary bg-primary/5"
                : "border-border hover:border-primary/40 hover:bg-accent",
            )}
          >
            <FontAwesomeIcon icon={c.icon} className="mt-0.5 size-4 text-muted-foreground" />
            <span>
              <span className="block text-sm font-medium">{c.label}</span>
              <span className="mt-1 block text-xs text-muted-foreground">{c.description}</span>
            </span>
          </button>
        ))}
      </div>

      {choice === "git" ? <GitDeployForm environmentId={environmentId} /> : null}
      {choice === "template" ? (
        <AppMarketplace
          templates={templates}
          installedProjects={installedProjects}
          environmentId={environmentId}
        />
      ) : null}
      {choice === "database" ? (
        <DatabaseCreateForm engines={engines} environmentId={environmentId} />
      ) : null}
    </section>
  )
}
