"use client"

import { useEffect, useRef, useState } from "react"

import { cn } from "@/lib/utils"
import type { DeploymentLogLine } from "@/lib/types"

type StreamPhase = "connecting" | "streaming" | "done" | "error"

function statusTone(status: string): string {
  const normalized = status.toLowerCase()
  if (/(fail|error|cancel)/.test(normalized)) {
    return "border-status-err/25 bg-status-err/10 text-status-err"
  }
  if (/(finish|success|succeed|deployed)/.test(normalized)) {
    return "border-status-ok/25 bg-status-ok/10 text-status-ok"
  }
  if (/(build|progress|queue|running|deploy|start)/.test(normalized)) {
    return "border-status-warn/25 bg-status-warn/10 text-status-warn"
  }
  return "border-border bg-background text-muted-foreground"
}

export function LogStream({
  applicationId,
  deploymentId,
}: {
  applicationId: string
  deploymentId: string
}) {
  const [lines, setLines] = useState<DeploymentLogLine[]>([])
  const [status, setStatus] = useState<string>("")
  const [phase, setPhase] = useState<StreamPhase>("connecting")
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const doneRef = useRef(false)

  useEffect(() => {
    // This component is remounted via `key` when the deployment changes, so
    // state starts fresh on each mount; the effect only owns the connection.
    const source = new EventSource(
      `/api/stream/projects/${applicationId}/deployments/${deploymentId}/logs/stream`,
    )

    source.addEventListener("status", (event) => {
      const data = JSON.parse((event as MessageEvent).data) as { status: string }
      setStatus(data.status)
      setPhase("streaming")
    })

    source.addEventListener("log", (event) => {
      const line = JSON.parse((event as MessageEvent).data) as DeploymentLogLine
      setLines((prev) => [...prev, line])
      setPhase("streaming")
    })

    source.addEventListener("done", (event) => {
      const data = JSON.parse((event as MessageEvent).data) as { status: string }
      setStatus(data.status)
      setPhase("done")
      doneRef.current = true
      source.close()
    })

    source.addEventListener("error", () => {
      // The browser also fires a native "error" when the server closes the
      // stream after "done"; only surface a real failure if we weren't done.
      if (!doneRef.current) {
        setPhase("error")
      }
      source.close()
    })

    return () => {
      source.close()
    }
  }, [applicationId, deploymentId])

  useEffect(() => {
    const node = scrollRef.current
    if (node) {
      node.scrollTop = node.scrollHeight
    }
  }, [lines])

  const isLive = phase === "connecting" || phase === "streaming"

  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-card">
      <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
        <div className="flex items-center gap-2">
          {isLive ? (
            <span className="h-2 w-2 animate-pulse rounded-full bg-status-warn" aria-hidden />
          ) : null}
          <span className="text-sm font-medium text-foreground">Build logs</span>
          <span className="font-mono text-xs text-muted-foreground">{deploymentId.slice(0, 12)}</span>
        </div>
        <span
          className={cn(
            "inline-flex rounded-full border px-3 py-1 text-xs font-medium",
            statusTone(status || phase),
          )}
        >
          {phase === "connecting" && !status
            ? "Connecting…"
            : phase === "error"
              ? "Stream error"
              : status || "Streaming…"}
        </span>
      </div>
      <div
        ref={scrollRef}
        data-testid="log-output"
        className="max-h-[28rem] overflow-y-auto bg-black px-4 py-3 font-mono text-xs leading-relaxed"
      >
        {lines.length === 0 ? (
          <p className="text-muted-foreground">
            {phase === "error" ? "Could not load logs for this deployment." : "Waiting for output…"}
          </p>
        ) : (
          lines.map((line, index) => (
            <div
              key={index}
              className={cn(
                "whitespace-pre-wrap break-words",
                line.type === "stderr" ? "text-red-300" : "text-zinc-300",
              )}
            >
              {line.output}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
