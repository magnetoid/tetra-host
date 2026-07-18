import { ApiError, fetchBackend } from "@/lib/api"

export type DegradedResult<T> = {
  data: T
  /** Human label of the failed source, or null when the fetch succeeded. */
  degraded: string | null
}

type Options = Parameters<typeof fetchBackend>[1]

/**
 * Server-side fetch that degrades visibly instead of silently. On failure it
 * returns the fallback **plus** the failed source's label so pages can render a
 * "provider unreachable" banner — an outage must never be indistinguishable
 * from "no data" (the old `.catch(() => fallback)` pattern).
 */
export async function fetchDegraded<T>(
  path: string,
  source: string,
  fallback: T,
  options?: Options,
): Promise<DegradedResult<T>> {
  try {
    const data = await fetchBackend<T>(path, options)
    return { data, degraded: null }
  } catch (err) {
    console.error(`[degraded] ${source} (${path}):`, err instanceof Error ? err.message : err)
    return {
      data: fallback,
      degraded:
        err instanceof ApiError ? `${source} (HTTP ${err.status})` : `${source} (unreachable)`,
    }
  }
}

/** Collect the non-null failure labels from a batch of degraded results. */
export function degradedSources(results: Array<DegradedResult<unknown>>): string[] {
  return [...new Set(results.map((r) => r.degraded).filter((d): d is string => d !== null))]
}
