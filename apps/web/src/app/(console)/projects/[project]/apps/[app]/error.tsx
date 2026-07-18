"use client"

import { RouteError } from "@/components/ui/route-error"

/** App-scoped boundary — keeps the app entity header + tab nav alive when a
 *  single tab (deployments/logs/metrics/…) fails to render. */
export default function AppError({
  error,
  unstable_retry,
}: {
  error: Error & { digest?: string }
  unstable_retry: () => void
}) {
  return <RouteError error={error} retry={unstable_retry} title="This tab failed to load" />
}
