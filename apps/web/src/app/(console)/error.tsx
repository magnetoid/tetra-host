"use client"

import { RouteError } from "@/components/ui/route-error"

/** Console-wide error boundary — keeps the shell (sidebar/topbar) alive and
 *  swaps only the page content for a recoverable fallback. */
export default function ConsoleError({
  error,
  unstable_retry,
}: {
  error: Error & { digest?: string }
  unstable_retry: () => void
}) {
  return <RouteError error={error} retry={unstable_retry} />
}
