"use client"

import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import { useRouter, usePathname } from "next/navigation"
import { useEffect, useMemo, useRef, useState } from "react"

import { faChevronDown, faCircleCheck, faLayerGroup, faServer } from "@/lib/icons"
import { cn } from "@/lib/utils"

type ProjectMeta = { id: string; name: string }

/**
 * The sidebar project selector — sits under the "Control plane" wordmark and scopes the whole
 * console to one project. Selecting a project routes into its Deployments; the sidebar nav
 * (ConsoleNav) then slides to that project's menu. "Platform" returns to the global view.
 */
export function SidebarProjectSelector({ projects }: { projects: ProjectMeta[] }) {
  const router = useRouter()
  const pathname = usePathname()
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const ref = useRef<HTMLDivElement>(null)

  const activeId = /^\/projects\/([^/]+)(?:\/|$)/.exec(pathname)?.[1]
  const activeName = activeId ? projects.find((p) => p.id === activeId)?.name : undefined

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return needle ? projects.filter((p) => p.name.toLowerCase().includes(needle)) : projects
  }, [projects, query])

  useEffect(() => {
    if (!open) return
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false)
    }
    document.addEventListener("mousedown", onClick)
    document.addEventListener("keydown", onKey)
    return () => {
      document.removeEventListener("mousedown", onClick)
      document.removeEventListener("keydown", onKey)
    }
  }, [open])

  function go(href: string) {
    setOpen(false)
    setQuery("")
    router.push(href)
  }

  return (
    <div className="relative mt-6" ref={ref}>
      <span className="mb-1.5 block px-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
        Project
      </span>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        className={cn(
          "flex w-full items-center gap-2 rounded-xl border px-3 py-2.5 text-sm transition",
          activeId ? "border-primary/40 bg-primary/5" : "border-border bg-background/60",
          "hover:border-primary/40",
        )}
      >
        <FontAwesomeIcon
          icon={activeId ? faServer : faLayerGroup}
          className="h-3.5 w-3.5 shrink-0 text-primary"
        />
        <span className="min-w-0 flex-1 truncate text-left font-medium">
          {activeName ?? "Platform"}
        </span>
        <FontAwesomeIcon
          icon={faChevronDown}
          className={cn("h-3 w-3 shrink-0 text-muted-foreground transition-transform", open && "rotate-180")}
        />
      </button>

      {open ? (
        <div
          role="menu"
          className="absolute left-0 right-0 z-50 mt-2 overflow-hidden rounded-xl border border-border bg-card shadow-2xl"
        >
          {projects.length > 6 ? (
            <div className="border-b border-border p-2">
              <input
                autoFocus
                aria-label="Search projects"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search…"
                className="w-full rounded-md border border-border bg-background px-2.5 py-1.5 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/25"
              />
            </div>
          ) : null}

          <div className="p-1.5">
            <button
              type="button"
              role="menuitem"
              onClick={() => go("/dashboard")}
              className={cn(
                "flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm transition hover:bg-accent",
                !activeId && "bg-accent font-medium",
              )}
            >
              <FontAwesomeIcon icon={faLayerGroup} className="h-3.5 w-3.5 text-muted-foreground" fixedWidth />
              <span className="flex-1">Platform</span>
              {!activeId ? <FontAwesomeIcon icon={faCircleCheck} className="h-3 w-3 text-primary" /> : null}
            </button>
          </div>

          <div className="max-h-72 overflow-y-auto border-t border-border p-1.5">
            {filtered.length === 0 ? (
              <div className="px-3 py-2 text-sm text-muted-foreground">No projects found.</div>
            ) : (
              filtered.map((p) => {
                const active = p.id === activeId
                return (
                  <button
                    key={p.id}
                    type="button"
                    role="menuitem"
                    onClick={() => go(`/projects/${p.id}/deployments`)}
                    className={cn(
                      "flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm transition hover:bg-accent",
                      active && "bg-accent font-medium",
                    )}
                  >
                    <span className="grid size-6 shrink-0 place-items-center rounded-md border border-border bg-background font-mono text-[10px] font-semibold">
                      {p.name.slice(0, 2).toUpperCase()}
                    </span>
                    <span className="min-w-0 flex-1 truncate">{p.name}</span>
                    {active ? <FontAwesomeIcon icon={faCircleCheck} className="h-3 w-3 text-primary" /> : null}
                  </button>
                )
              })
            )}
          </div>
        </div>
      ) : null}
    </div>
  )
}
