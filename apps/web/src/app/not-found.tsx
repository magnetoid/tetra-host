import Link from "next/link"

import { Button } from "@/components/ui/button"

/** Root 404 — rendered for unmatched URLs and `notFound()` throws. */
export default function NotFound() {
  return (
    <div className="mx-auto flex min-h-[60vh] max-w-lg flex-col items-center justify-center gap-4 px-6 text-center">
      <p className="font-mono text-xs uppercase tracking-[0.2em] text-muted-foreground">404</p>
      <h1 className="text-2xl font-semibold tracking-tight">This page does not exist</h1>
      <p className="text-sm text-muted-foreground">
        The resource may have been removed, renamed, or you may not have access to it in this
        workspace.
      </p>
      <div className="flex items-center gap-2">
        <Button variant="primary" asChild>
          <Link href="/dashboard">Go to overview</Link>
        </Button>
        <Button variant="secondary" asChild>
          <Link href="/projects">View projects</Link>
        </Button>
      </div>
    </div>
  )
}
