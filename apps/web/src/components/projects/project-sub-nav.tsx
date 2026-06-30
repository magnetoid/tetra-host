"use client"

import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import Link from "next/link"
import { usePathname } from "next/navigation"

import {
  faBug,
  faChartLine,
  faEarthAmericas,
  faGear,
  faKey,
  faListCheck,
  faTableColumns,
  faTerminal,
} from "@/lib/icons"
import { cn } from "@/lib/utils"

type SubNavItem = {
  href: string
  label: string
  icon: typeof faTableColumns
  /** When true, only the exact path matches (no prefix match). */
  exact?: boolean
}

function buildItems(projectId: string): SubNavItem[] {
  const base = `/projects/${projectId}`
  return [
    { href: base, label: "Overview", icon: faTableColumns, exact: true },
    { href: `${base}/deployments`, label: "Deployments", icon: faListCheck },
    { href: `${base}/logs`, label: "Logs", icon: faTerminal },
    { href: `${base}/env`, label: "Env", icon: faKey },
    { href: `${base}/domains`, label: "Domains", icon: faEarthAmericas },
    { href: `${base}/metrics`, label: "Metrics", icon: faChartLine },
    { href: `${base}/errors`, label: "Errors", icon: faBug },
    { href: `${base}/settings`, label: "Settings", icon: faGear },
  ]
}

export function ProjectSubNav({
  projectId,
  projectName,
}: {
  projectId: string
  projectName: string
}) {
  const pathname = usePathname()
  const items = buildItems(projectId)

  return (
    <aside className="flex shrink-0 flex-col gap-1 text-sm">
      <div className="mb-3 px-3">
        <p className="text-xs font-medium uppercase tracking-wider text-zinc-500">Project</p>
        <h2 className="mt-1 truncate text-base font-semibold text-zinc-100">{projectName}</h2>
      </div>

      <nav className="space-y-0.5">
        {items.map((item) => {
          const active = item.exact ? pathname === item.href : pathname.startsWith(item.href)
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-zinc-300 transition hover:bg-zinc-800 hover:text-white",
                active && "bg-zinc-800 text-white",
              )}
            >
              <FontAwesomeIcon
                icon={item.icon}
                className={cn("h-4 w-4 shrink-0", active ? "text-primary" : "text-zinc-500")}
                fixedWidth
              />
              {item.label}
            </Link>
          )
        })}
      </nav>
    </aside>
  )
}
