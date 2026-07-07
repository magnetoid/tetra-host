"use client"

import { useMemo, useState } from "react"
import { useRouter } from "next/navigation"

import { AlertBanner } from "@/components/ui/alert-banner"
import { Button } from "@/components/ui/button"
import { Modal } from "@/components/ui/modal"
import { faCircleCheck, faPlus, faTag } from "@/lib/icons"
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import type { AppTemplate } from "@/lib/types"

const LOGO_BASE = "https://cdn.jsdelivr.net/gh/coollabsio/coolify@main/public/"
const MAX_CARDS = 60

export function AppMarketplace({
  templates,
  installedProjects,
}: {
  templates: AppTemplate[]
  installedProjects: string[]
}) {
  const router = useRouter()
  const [query, setQuery] = useState("")
  const [category, setCategory] = useState("all")
  const [installing, setInstalling] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<AppTemplate | null>(null)

  const categories = useMemo(() => {
    const set = new Set<string>()
    templates.forEach((t) => t.category && set.add(t.category))
    return ["all", ...Array.from(set).sort()]
  }, [templates])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return templates.filter((t) => {
      if (category !== "all" && t.category !== category) return false
      if (!q) return true
      return `${t.name} ${t.description} ${t.tags.join(" ")}`.toLowerCase().includes(q)
    })
  }, [templates, query, category])

  const shown = filtered.slice(0, MAX_CARDS)

  async function install(slug: string) {
    setInstalling(slug)
    setMessage(null)
    setError(null)
    try {
      const response = await fetch("/api/proxy/apps/install", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ slug }),
      })
      const payload = (await response.json().catch(() => ({}))) as { message?: string; detail?: string }
      if (!response.ok) {
        setError(payload.detail ?? "Install failed.")
        return
      }
      setMessage(payload.message ?? "App installed.")
      setSelected(null)
      router.refresh()
    } catch {
      setError("Unable to reach the control plane.")
    } finally {
      setInstalling(null)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <input
          aria-label="Search apps"
          placeholder="Search apps…"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          className="w-64 rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none"
        />
        <select
          aria-label="Category"
          value={category}
          onChange={(event) => setCategory(event.target.value)}
          className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none"
        >
          {categories.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
        <span className="text-sm text-muted-foreground">{filtered.length} apps</span>
      </div>

      {message ? <AlertBanner tone="success">{message}</AlertBanner> : null}
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {shown.map((template) => {
          const installed = installedProjects.includes(template.slug)
          return (
            <button
              key={template.slug}
              type="button"
              onClick={() => setSelected(template)}
              aria-label={`View details for ${template.name}`}
              className="flex flex-col gap-3 rounded-2xl border border-border bg-muted p-4 text-left transition-colors hover:border-primary/40 hover:bg-accent focus:border-primary focus:outline-none"
            >
              <div className="flex items-start gap-3">
                <AppLogo template={template} />
                <div className="min-w-0 flex-1">
                  <div className="truncate font-medium">{template.name}</div>
                  <div className="text-xs text-muted-foreground">{template.category}</div>
                </div>
                {installed ? (
                  <FontAwesomeIcon icon={faCircleCheck} className="h-4 w-4 shrink-0 text-status-ok" />
                ) : null}
              </div>
              <p className="line-clamp-2 min-h-[2.5rem] text-sm text-muted-foreground">{template.description}</p>
              <span className="mt-auto text-xs font-medium text-primary">
                {installed ? "Installed — view details" : "View details"}
              </span>
            </button>
          )
        })}
      </div>

      {filtered.length > MAX_CARDS ? (
        <p className="text-sm text-muted-foreground">
          Showing {MAX_CARDS} of {filtered.length} — refine your search to narrow it down.
        </p>
      ) : null}
      {filtered.length === 0 ? <p className="text-sm text-muted-foreground">No apps match your search.</p> : null}

      <AppDetailModal
        template={selected}
        installed={selected ? installedProjects.includes(selected.slug) : false}
        installing={selected ? installing === selected.slug : false}
        busy={installing !== null}
        onOpenChange={(open) => {
          if (!open) setSelected(null)
        }}
        onInstall={install}
      />
    </div>
  )
}

function AppDetailModal({
  template,
  installed,
  installing,
  busy,
  onOpenChange,
  onInstall,
}: {
  template: AppTemplate | null
  installed: boolean
  installing: boolean
  busy: boolean
  onOpenChange: (open: boolean) => void
  onInstall: (slug: string) => void
}) {
  return (
    <Modal
      open={template !== null}
      onOpenChange={onOpenChange}
      title={
        template ? (
          <span className="flex items-center gap-3">
            <AppLogo template={template} />
            <span className="truncate">{template.name}</span>
          </span>
        ) : (
          ""
        )
      }
      description={template?.category}
      footer={
        template ? (
          <>
            <Button variant="ghost" onClick={() => onOpenChange(false)}>
              Close
            </Button>
            <Button
              variant={installed ? "secondary" : "primary"}
              icon={installed ? faCircleCheck : faPlus}
              disabled={installed || busy}
              onClick={() => onInstall(template.slug)}
            >
              {installed ? "Installed" : installing ? "Installing…" : "Install"}
            </Button>
          </>
        ) : null
      }
    >
      {template ? (
        <div className="space-y-5">
          <p className="text-sm leading-relaxed text-foreground">
            {template.description || "No description provided."}
          </p>

          {template.tags.length > 0 ? (
            <div className="flex flex-wrap items-center gap-2">
              {template.tags.map((tag) => (
                <span
                  key={tag}
                  className="inline-flex items-center gap-1.5 rounded-full border border-border bg-background px-2.5 py-1 text-xs text-muted-foreground"
                >
                  <FontAwesomeIcon icon={faTag} className="h-3 w-3" />
                  {tag}
                </span>
              ))}
            </div>
          ) : null}

          <dl className="grid grid-cols-1 gap-3 border-t border-border pt-4 sm:grid-cols-2">
            <div>
              <dt className="text-xs uppercase tracking-wide text-muted-foreground">Slug</dt>
              <dd className="mt-1 font-mono text-sm">{template.slug}</dd>
            </div>
            {template.port ? (
              <div>
                <dt className="text-xs uppercase tracking-wide text-muted-foreground">Port</dt>
                <dd className="mt-1 font-mono text-sm">{template.port}</dd>
              </div>
            ) : null}
          </dl>
        </div>
      ) : null}
    </Modal>
  )
}

function AppLogo({ template }: { template: AppTemplate }) {
  const [failed, setFailed] = useState(false)
  const initial = template.name.charAt(0).toUpperCase()
  return (
    <div className="grid h-10 w-10 shrink-0 place-items-center overflow-hidden rounded-lg border border-border bg-background text-sm font-semibold text-muted-foreground">
      {template.logo && !failed ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={`${LOGO_BASE}${template.logo}`}
          alt=""
          loading="lazy"
          className="h-6 w-6 object-contain"
          onError={() => setFailed(true)}
        />
      ) : (
        initial
      )}
    </div>
  )
}
