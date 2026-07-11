"use client"

import { useCallback, useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import * as Dialog from "@radix-ui/react-dialog"
import { Command } from "cmdk"
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"

import { consoleNavItems, NAV_SECTIONS } from "@/lib/navigation"
import { projectSlug } from "@/lib/projects"
import { toggleTheme } from "@/lib/theme"
import {
  faArrowRightFromBracket,
  faArrowUpRightFromSquare,
  faMagnifyingGlass,
  faMoon,
  faServer,
} from "@/lib/icons"

type ProjectLite = { id: string; name: string; slug: string }

/**
 * ⌘K command palette — global search + actions (navigation, project jump, theme, docs,
 * sign out). Opens on ⌘/Ctrl-K anywhere or via the topbar trigger. Radix Dialog gives the
 * focus trap + Esc; cmdk gives the ARIA combobox + fuzzy filtering. Nav model is reused
 * from lib/navigation; projects are fetched lazily on first open.
 */
export function CommandMenu({ adminRole }: { adminRole?: string }) {
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [projects, setProjects] = useState<ProjectLite[]>([])

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault()
        setOpen((value) => !value)
      }
    }
    document.addEventListener("keydown", onKey)
    return () => document.removeEventListener("keydown", onKey)
  }, [])

  useEffect(() => {
    if (!open || projects.length > 0) return
    let active = true
    fetch("/api/proxy/projects", { headers: { Accept: "application/json" } })
      .then((res) => (res.ok ? res.json() : []))
      .then((data: (ProjectLite & Parameters<typeof projectSlug>[0])[]) => {
        if (active && Array.isArray(data)) {
          setProjects(data.map((p) => ({ id: p.id, name: p.name, slug: projectSlug(p) })))
        }
      })
      .catch(() => {})
    return () => {
      active = false
    }
  }, [open, projects.length])

  const run = useCallback((fn: () => void) => {
    setOpen(false)
    fn()
  }, [])
  const go = useCallback((href: string) => run(() => router.push(href)), [run, router])

  const navItems = consoleNavItems.filter(
    (item) => !item.platformAdminOnly || adminRole === "platform_admin",
  )

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex items-center gap-2 rounded-lg border border-border bg-background/60 px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:border-primary/30 hover:text-foreground"
      >
        <FontAwesomeIcon icon={faMagnifyingGlass} className="h-3.5 w-3.5" />
        <span className="hidden sm:inline">Search…</span>
        <kbd className="ml-1 hidden rounded border border-border bg-muted px-1.5 font-mono text-[10px] text-muted-foreground sm:inline">
          ⌘K
        </kbd>
      </button>

      <Dialog.Root open={open} onOpenChange={setOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-background/70 backdrop-blur-sm data-[state=open]:animate-in" />
          <Dialog.Content
            className="fixed left-1/2 top-[18%] z-50 w-[92vw] max-w-xl -translate-x-1/2 overflow-hidden rounded-2xl border border-border bg-popover shadow-2xl"
            aria-label="Command menu"
          >
            <Dialog.Title className="sr-only">Command menu</Dialog.Title>
            <Command
              loop
              className="[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:font-mono [&_[cmdk-group-heading]]:text-[10px] [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:text-muted-foreground"
            >
              <div className="flex items-center gap-2 border-b border-border px-4">
                <FontAwesomeIcon icon={faMagnifyingGlass} className="h-4 w-4 text-muted-foreground" />
                <Command.Input
                  placeholder="Search projects, pages, actions…"
                  className="w-full bg-transparent py-3.5 text-sm outline-none placeholder:text-muted-foreground"
                />
              </div>
              <Command.List className="max-h-80 overflow-y-auto p-2">
                <Command.Empty className="py-6 text-center text-sm text-muted-foreground">
                  No results.
                </Command.Empty>

                {NAV_SECTIONS.map((section) => {
                  const items = navItems.filter((item) => item.section === section)
                  if (items.length === 0) return null
                  return (
                    <Command.Group key={section} heading={section}>
                      {items.map((item) => (
                        <Command.Item
                          key={item.href}
                          value={`${section} ${item.label}`}
                          onSelect={() => go(item.href)}
                          className="flex cursor-pointer items-center gap-2.5 rounded-lg px-2 py-2 text-sm text-foreground data-[selected=true]:bg-accent"
                        >
                          {item.icon ? (
                            <FontAwesomeIcon
                              icon={item.icon}
                              className="h-4 w-4 text-muted-foreground"
                              fixedWidth
                            />
                          ) : null}
                          {item.label}
                        </Command.Item>
                      ))}
                    </Command.Group>
                  )
                })}

                {projects.length > 0 ? (
                  <Command.Group heading="Projects">
                    {projects.map((project) => (
                      <Command.Item
                        key={project.id}
                        value={`project ${project.name}`}
                        onSelect={() => go(`/projects/${project.slug}/apps/${project.id}`)}
                        className="flex cursor-pointer items-center gap-2.5 rounded-lg px-2 py-2 text-sm text-foreground data-[selected=true]:bg-accent"
                      >
                        <FontAwesomeIcon
                          icon={faServer}
                          className="h-4 w-4 text-muted-foreground"
                          fixedWidth
                        />
                        <span className="truncate">{project.name}</span>
                      </Command.Item>
                    ))}
                  </Command.Group>
                ) : null}

                <Command.Group heading="Actions">
                  <Action icon={faMoon} label="Toggle theme" onSelect={() => run(() => toggleTheme())} />
                  <Action icon={faArrowUpRightFromSquare} label="Open docs" onSelect={() => go("/docs")} />
                  <Action
                    icon={faArrowRightFromBracket}
                    label="Sign out"
                    onSelect={() =>
                      run(() => {
                        fetch("/api/auth/logout", { method: "POST" }).finally(() => {
                          window.location.href = "/auth/login"
                        })
                      })
                    }
                  />
                </Command.Group>
              </Command.List>
            </Command>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </>
  )
}

function Action({
  icon,
  label,
  onSelect,
}: {
  icon: typeof faMoon
  label: string
  onSelect: () => void
}) {
  return (
    <Command.Item
      value={`action ${label}`}
      onSelect={onSelect}
      className="flex cursor-pointer items-center gap-2.5 rounded-lg px-2 py-2 text-sm text-foreground data-[selected=true]:bg-accent"
    >
      <FontAwesomeIcon icon={icon} className="h-4 w-4 text-muted-foreground" fixedWidth />
      {label}
    </Command.Item>
  )
}
