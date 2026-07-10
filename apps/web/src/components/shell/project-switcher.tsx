"use client"

import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { useEffect, useMemo, useRef, useState } from "react"

import { faChevronDown, faCircleCheck, faLayerGroup } from "@/lib/icons"
import { cn } from "@/lib/utils"

type ProjectMeta = { id: string; name: string }

/**
 * The upper-right project switcher — jump straight to any project's Deployments
 * without going back to the list (Vercel-style). Headless popover (no Radix dep):
 * button trigger + outside-click / Escape close, mirroring {@link UserMenu}. The
 * active project is derived from the path so it stays correct on every navigation.
 */
export function ProjectSwitcher({ projects }: { projects: ProjectMeta[] }) {
  const pathname = usePathname()
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const ref = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)

  const activeId = /^\/projects\/([^/]+)(?:\/|$)/.exec(pathname)?.[1]
  const activeName = activeId ? projects.find((p) => p.id === activeId)?.name : undefined

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return projects
    return projects.filter((p) => p.name.toLowerCase().includes(needle))
  }, [projects, query])

  useEffect(() => {
    if (!open) return
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setOpen(false)
        triggerRef.current?.focus()
      }
    }
    document.addEventListener("mousedown", onClick)
    document.addEventListener("keydown", onKey)
    return () => {
      document.removeEventListener("mousedown", onClick)
      document.removeEventListener("keydown", onKey)
    }
  }, [open])

  return (
    <div className="relative" ref={ref}>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex max-w-[12rem] items-center gap-2 rounded-md border border-border px-2.5 py-1.5 text-sm transition hover:bg-accent"
      >
        <FontAwesomeIcon icon={faLayerGroup} className="h-3.5 w-3.5 shrink-0 text-primary" />
        <span className="truncate">{activeName ?? "Projects"}</span>
        <FontAwesomeIcon icon={faChevronDown} className="h-3 w-3 shrink-0 text-muted-foreground" />
      </button>

      {open ? (
        <div
          role="menu"
          className="absolute right-0 z-50 mt-2 w-72 overflow-hidden rounded-xl border border-border bg-card shadow-2xl"
        >
          {projects.length > 6 ? (
            <div className="border-b border-border p-2">
              <input
                autoFocus
                aria-label="Search projects"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search projects…"
                className="w-full rounded-md border border-border bg-background px-2.5 py-1.5 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/25"
              />
            </div>
          ) : null}

          <div className="max-h-72 overflow-y-auto p-1.5">
            {filtered.length === 0 ? (
              <div className="px-3 py-2 text-sm text-muted-foreground">No projects found.</div>
            ) : (
              filtered.map((project) => {
                const active = project.id === activeId
                return (
                  <Link
                    key={project.id}
                    href={`/projects/${project.id}/deployments`}
                    role="menuitem"
                    onClick={() => setOpen(false)}
                    className={cn(
                      "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition hover:bg-accent",
                      active && "bg-accent font-medium",
                    )}
                  >
                    <span className="grid size-6 shrink-0 place-items-center rounded-md border border-border bg-background font-mono text-[10px] font-semibold">
                      {project.name.slice(0, 2).toUpperCase()}
                    </span>
                    <span className="truncate">{project.name}</span>
                    {active ? (
                      <FontAwesomeIcon icon={faCircleCheck} className="ml-auto h-3 w-3 text-primary" />
                    ) : null}
                  </Link>
                )
              })
            )}
          </div>

          <div className="border-t border-border p-1.5">
            <Link
              href="/projects"
              role="menuitem"
              onClick={() => setOpen(false)}
              className="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-muted-foreground transition hover:bg-accent hover:text-foreground"
            >
              <FontAwesomeIcon icon={faLayerGroup} className="h-3.5 w-3.5" fixedWidth />
              All projects
            </Link>
          </div>
        </div>
      ) : null}
    </div>
  )
}
