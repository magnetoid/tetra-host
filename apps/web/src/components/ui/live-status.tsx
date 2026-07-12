"use client"

import { useRouter } from "next/navigation"
import { useEffect, useState } from "react"

import { AppStatus } from "@/components/ui/app-status"
import { isDeploymentActive } from "@/lib/deploy-stats"
import type { ProjectDeploymentRecord } from "@/lib/types"

/**
 * App status that goes live during a deploy: shows a pulsing "Deploying" while a
 * build is in flight, polling the deployment list, then flips to the real
 * container status (Running/Failed) the moment it finishes — no manual refresh.
 */
export function LiveStatus({
  appId,
  status,
  deploying,
}: {
  appId: string
  status: string
  deploying: boolean
}) {
  const router = useRouter()
  const [isDeploying, setIsDeploying] = useState(deploying)

  useEffect(() => {
    if (!isDeploying) return
    let cancelled = false
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/proxy/projects/${appId}/deployments`, {
          headers: { Accept: "application/json" },
        })
        if (!res.ok) return
        const deployments = (await res.json()) as ProjectDeploymentRecord[]
        const latest = Array.isArray(deployments)
          ? deployments.reduce<ProjectDeploymentRecord | null>(
              (newest, d) => (!newest || d.created_at > newest.created_at ? d : newest),
              null,
            )
          : null
        if (!cancelled && (!latest || !isDeploymentActive(latest.status))) {
          setIsDeploying(false)
          router.refresh()
        }
      } catch {
        // transient — keep polling
      }
    }, 5000)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [isDeploying, appId, router])

  return <AppStatus value={isDeploying ? "deploying" : status} />
}
