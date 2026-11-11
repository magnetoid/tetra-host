"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { Fragment } from "react"

import { useScopeLabels } from "@/components/shell/scope-labels"
import { breadcrumbsFor, resolveScope } from "@/lib/navigation"

/** Platform / team / project / app [/ page] — every crumb but the last is a link. */
export function Breadcrumbs({ isPlatformAdmin }: { isPlatformAdmin: boolean }) {
  const pathname = usePathname()
  const labels = useScopeLabels()
  const crumbs = breadcrumbsFor(resolveScope(pathname, isPlatformAdmin), pathname, isPlatformAdmin, labels)

  return (
    <nav aria-label="Breadcrumb" className="min-w-0">
      <ol className="flex min-w-0 items-center gap-0.5 text-sm">
        {crumbs.map((crumb, index) => (
          <Fragment key={`${crumb.label}-${index}`}>
            {index > 0 ? (
              <li aria-hidden className="px-0.5 text-muted-foreground/50">
                /
              </li>
            ) : null}
            <li className={index < crumbs.length - 2 ? "hidden min-w-0 sm:block" : "min-w-0"}>
              {crumb.href ? (
                <Link
                  href={crumb.href}
                  className="block truncate rounded-md px-1.5 py-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                >
                  {crumb.label}
                </Link>
              ) : (
                <span aria-current="page" className="block truncate px-1.5 py-1 font-medium">
                  {crumb.label}
                </span>
              )}
            </li>
          </Fragment>
        ))}
      </ol>
    </nav>
  )
}
