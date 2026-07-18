"use client"

import { useRouter } from "next/navigation"
import { useCallback, useState } from "react"
import { toast } from "sonner"

import { ClientApiError } from "@/lib/client-api"

type RunOptions = {
  /** Key identifying which control is busy (row id, "add", …). Defaults to "default". */
  key?: string
  /** Refresh server components after success (default true). */
  refresh?: boolean
  /** Toast this on success (non-blocking confirmation). */
  successMessage?: string
  onSuccess?: () => void
}

/**
 * The console's one mutation hook: pending/error state + router.refresh(),
 * replacing the ~15-line try/catch/finally block previously copy-pasted across
 * ~33 client components. Works with any async fn; pairs with `apiFetch`.
 */
export function useAction() {
  const router = useRouter()
  const [pending, setPending] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const run = useCallback(
    async (fn: () => Promise<unknown>, options: RunOptions = {}) => {
      setError(null)
      setPending(options.key ?? "default")
      try {
        await fn()
        if (options.successMessage) {
          toast.success(options.successMessage)
        }
        options.onSuccess?.()
        if (options.refresh !== false) {
          router.refresh()
        }
        return true
      } catch (err) {
        setError(
          err instanceof ClientApiError || err instanceof Error
            ? err.message
            : "Something went wrong — please retry.",
        )
        return false
      } finally {
        setPending(null)
      }
    },
    [router],
  )

  return { run, pending, error, setError }
}
