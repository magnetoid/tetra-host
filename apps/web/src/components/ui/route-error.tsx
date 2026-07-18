"use client"

import { useEffect } from "react"

import { Button } from "@/components/ui/button"

/**
 * Shared route-boundary fallback used by every `error.tsx`. Announces itself to
 * assistive tech, logs the error (digest links it to server logs), and offers
 * recovery via Next's re-fetching retry.
 */
export function RouteError({
  error,
  retry,
  title = "Something went wrong",
}: {
  error: Error & { digest?: string }
  retry: () => void
  title?: string
}) {
  useEffect(() => {
    // Surface in the console (and, once wired, the browser error reporter).
    console.error(error)
  }, [error])

  return (
    <div
      role="alert"
      className="mx-auto flex min-h-[40vh] max-w-lg flex-col items-center justify-center gap-4 text-center"
    >
      <div className="grid size-12 place-items-center rounded-lg border border-destructive/30 bg-destructive/10 font-mono text-lg text-destructive">
        !
      </div>
      <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
      <p className="text-sm text-muted-foreground">
        The console hit an unexpected error rendering this page. This is usually transient — try
        again, and if it keeps happening check the provider status on the dashboard.
      </p>
      {error.digest ? (
        <p className="font-mono text-xs text-muted-foreground">ref {error.digest}</p>
      ) : null}
      <div className="flex items-center gap-2">
        <Button variant="primary" onClick={retry}>
          Try again
        </Button>
        <Button variant="secondary" asChild>
          <a href="/dashboard">Back to overview</a>
        </Button>
      </div>
    </div>
  )
}
