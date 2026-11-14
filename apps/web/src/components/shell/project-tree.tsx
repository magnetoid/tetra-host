"use client"

import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { useEffect, useRef, useState } from "react"

import { Collapsible } from "@/components/shell/collapsible"
import { useScopeLabels } from "@/components/shell/scope-labels"
import { apiFetch } from "@/lib/client-api"
import { faBox, faChevronRight, faDatabase, faFolder, faLayerGroup } from "@/lib/icons"
import { useNavOpen } from "@/lib/nav-state"
import { projectHref } from "@/lib/navigation"
import type { WorkspaceEnvironment, WorkspaceProject, WorkspaceService } from "@/lib/types"
import { cn } from "@/lib/utils"
import { serviceHref } from "@/lib/workspace"

/** Refetch at most this often while navigating, so new projects/services show up. */
const REFRESH_MS = 15_000

/** Where the current page sits, so the tree opens along that path. */
export function currentPlacement(
  pathname: string,
  labels: { projectSlug?: string; environmentSlug?: string },
): { project?: string; environment?: string } {
  const match = pathname.match(/^\/projects\/([^/]+)(?:\/([^/]+))?/)
  if (match) {
    return {
      project: decodeURIComponent(match[1]),
      environment: match[2] ? decodeURIComponent(match[2]) : undefined,
    }
  }
  return { project: labels.projectSlug, environment: labels.environmentSlug }
}

function Chevron({ open, onClick, label }: { open: boolean; onClick: () => void; label: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-expanded={open}
      aria-label={`${open ? "Collapse" : "Expand"} ${label}`}
      className="flex size-6 shrink-0 items-center justify-center rounded text-muted-foreground hover:bg-accent hover:text-foreground"
    >
      <FontAwesomeIcon
        icon={faChevronRight}
        className={cn("size-2.5 transition-transform duration-200 motion-reduce:transition-none", open && "rotate-90")}
      />
    </button>
  )
}

const ROW =
  "flex h-7 min-w-0 flex-1 items-center gap-2 rounded-md pr-2 text-[13px] transition-colors"

function rowTone(active: boolean): string {
  return active
    ? "bg-selected font-medium text-foreground"
    : "text-muted-foreground hover:bg-accent hover:text-foreground"
}

/** Team → project → environment → service, each level sliding open (ADR 0019). */
export function ProjectTree({ team, onNavigate }: { team: string; onNavigate?: () => void }) {
  const pathname = usePathname()
  const labels = useScopeLabels()
  const here = currentPlacement(pathname, labels)
  const [projects, setProjects] = useState<WorkspaceProject[] | null>(null)
  const [services, setServices] = useState<WorkspaceService[]>([])
  const [failed, setFailed] = useState(false)
  const loadedAt = useRef(0)

  useEffect(() => {
    if (!team || Date.now() - loadedAt.current < REFRESH_MS) return
    loadedAt.current = Date.now()
    let cancelled = false
    Promise.all([
      apiFetch<WorkspaceProject[]>(`/api/proxy/teams/${team}/projects`),
      apiFetch<WorkspaceService[]>(`/api/proxy/teams/${team}/apps`),
    ])
      .then(([p, s]) => {
        if (cancelled) return
        setProjects(p)
        setServices(s)
        setFailed(false)
      })
      .catch(() => {
        if (!cancelled) setFailed(true)
      })
    return () => {
      cancelled = true
    }
  }, [team, pathname])

  if (failed && projects === null) {
    return <p className="px-3 py-1 text-xs text-muted-foreground">Couldn&apos;t load projects.</p>
  }
  if (projects === null) {
    return (
      <div className="space-y-1.5 py-1 pl-7 pr-2" aria-hidden>
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-4 animate-pulse rounded bg-muted" />
        ))}
      </div>
    )
  }
  if (projects.length === 0) {
    return <p className="py-1 pl-8 text-xs text-muted-foreground">No projects yet.</p>
  }

  return (
    <ul className="flex flex-col gap-px py-0.5 pl-3" role="tree" aria-label="Projects">
      {projects.map((project) => (
        <ProjectNode
          key={project.id}
          team={team}
          project={project}
          services={services.filter((s) => s.project.slug === project.slug)}
          current={here.project === project.slug}
          currentEnvironment={here.project === project.slug ? here.environment : undefined}
          pathname={pathname}
          onNavigate={onNavigate}
        />
      ))}
    </ul>
  )
}

function ProjectNode({
  team,
  project,
  services,
  current,
  currentEnvironment,
  pathname,
  onNavigate,
}: {
  team: string
  project: WorkspaceProject
  services: WorkspaceService[]
  current: boolean
  currentEnvironment?: string
  pathname: string
  onNavigate?: () => void
}) {
  const [open, toggle] = useNavOpen(`project:${project.id}`, current)
  const [environments, setEnvironments] = useState<WorkspaceEnvironment[] | null>(null)
  const href = projectHref(project.slug)

  useEffect(() => {
    if (!open || environments) return
    let cancelled = false
    apiFetch<WorkspaceEnvironment[]>(
      `/api/proxy/teams/${team}/projects/${encodeURIComponent(project.slug)}/environments`,
    )
      .then((envs) => {
        if (!cancelled) setEnvironments(envs)
      })
      .catch(() => {
        if (!cancelled) setEnvironments([])
      })
    return () => {
      cancelled = true
    }
  }, [open, environments, team, project.slug])

  const onProjectPage = pathname === href || pathname === `${href}/`
  return (
    <li role="treeitem" aria-expanded={open} aria-selected={onProjectPage}>
      <div className="flex items-center">
        <Chevron open={open} onClick={toggle} label={project.name} />
        <Link href={href} onClick={onNavigate} className={cn(ROW, "pl-1", rowTone(onProjectPage))}>
          <FontAwesomeIcon icon={faFolder} className="size-3 shrink-0" />
          <span className="truncate">{project.name}</span>
        </Link>
      </div>
      <Collapsible open={open}>
        <ul role="group" className="ml-3 flex flex-col gap-px border-l border-border pl-1.5">
          {environments === null ? (
            <li className="h-6 py-1 pl-6">
              <div className="h-3.5 w-24 animate-pulse rounded bg-muted" />
            </li>
          ) : environments.length === 0 ? (
            <li className="py-1 pl-6 text-xs text-muted-foreground">No environments.</li>
          ) : (
            environments.map((env) => (
              <EnvironmentNode
                key={env.id}
                project={project}
                environment={env}
                services={services.filter((s) => s.environment.slug === env.slug)}
                current={currentEnvironment === env.slug}
                pathname={pathname}
                onNavigate={onNavigate}
              />
            ))
          )}
        </ul>
      </Collapsible>
    </li>
  )
}

function EnvironmentNode({
  project,
  environment,
  services,
  current,
  pathname,
  onNavigate,
}: {
  project: WorkspaceProject
  environment: WorkspaceEnvironment
  services: WorkspaceService[]
  current: boolean
  pathname: string
  onNavigate?: () => void
}) {
  const [open, toggle] = useNavOpen(`env:${environment.id}`, current)
  const href = projectHref(project.slug, environment.slug)
  return (
    <li role="treeitem" aria-expanded={open} aria-selected={pathname === href}>
      <div className="flex items-center">
        <Chevron open={open} onClick={toggle} label={environment.name} />
        <Link href={href} onClick={onNavigate} className={cn(ROW, "pl-1", rowTone(pathname === href))}>
          <FontAwesomeIcon icon={faLayerGroup} className="size-3 shrink-0" />
          <span className="truncate">{environment.name}</span>
          <span className="ml-auto text-[11px] tabular-nums text-muted-foreground">{services.length}</span>
        </Link>
      </div>
      <Collapsible open={open}>
        <ul role="group" className="ml-3 flex flex-col gap-px border-l border-border pl-1.5">
          {services.length === 0 ? (
            <li className="py-1 pl-2 text-xs text-muted-foreground">
              <Link href={href} onClick={onNavigate} className="hover:text-foreground">
                + New service
              </Link>
            </li>
          ) : (
            services.map((service) => {
              const target = serviceHref(service)
              const base = target.replace(/\/deployments$/, "")
              const active = pathname === base || pathname.startsWith(`${base}/`)
              return (
                <li key={service.id} role="treeitem" aria-selected={active}>
                  <Link href={target} onClick={onNavigate} className={cn(ROW, "pl-2", rowTone(active))}>
                    <FontAwesomeIcon
                      icon={service.kind === "database" ? faDatabase : faBox}
                      className="size-3 shrink-0"
                    />
                    <span className="truncate">{service.name}</span>
                  </Link>
                </li>
              )
            })
          )}
        </ul>
      </Collapsible>
    </li>
  )
}
