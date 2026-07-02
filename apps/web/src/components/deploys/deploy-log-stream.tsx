"use client"

import { useEffect, useRef, useState } from "react"

import { cn } from "@/lib/utils"

type StreamPhase = "connecting" | "streaming" | "done" | "error"

function statusTone(status: string): string {
  const normalized = status.toLowerCase()
  if (/(error|fail)/.test(normalized)) return "border-red-900 bg-red-950 text-red-200"
  if (/ready/.test(normalized)) return "border-emerald-900 bg-emerald-950 text-emerald-300"
  if (/(build|queue)/.test(normalized)) return "border-amber-900 bg-amber-950 text-amber-200"
  return "border-border bg-background text-zinc-400"
}

/** Live SSE build-log view for a native (Tetra Engine) deployment.
 *  Native `log` events carry a raw line string (unlike the Coolify stream's objects). */
export function DeployLogStream({ deploymentId }: { deploymentId: string }) {
  const [lines, setLines] = useState<string[]>([])
  const [status, setStatus] = useState<string>("")
  const [phase, setPhase] = useState<StreamPhase>("connecting")
  const scrollRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    const source = new EventSource(`/api/stream/deploys/${deploymentId}/logs/stream`)

    source.addEventListener("status", (event) => {
      const data = JSON.parse((event as MessageEvent).data) as { status: string }
      setStatus(data.status)
      setPhase("streaming")
    })
    source.addEventListener("log", (event) => {
      const line = JSON.parse((event as MessageEvent).data) as string
      setLines((prev) => [...prev, line])
      setPhase("streaming")
    })
    source.addEventListener("done", (event) => {
      const data = JSON.parse((event as MessageEvent).data) as { status: string }
      setStatus(data.status)
      setPhase("done")
      source.close()
    })
    source.addEventListener("error", () => {
      setPhase((current) => (current === "done" ? current : "error"))
      source.close()
    })
    return () => source.close()
  }, [deploymentId])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight })
  }, [lines])

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-xs">
        <span className={cn("rounded-full border px-2 py-0.5", statusTone(status))}>
          {status || "connecting…"}
        </span>
        {phase === "error" ? <span className="text-red-300">stream interrupted</span> : null}
      </div>
      <div
        ref={scrollRef}
        className="max-h-72 overflow-y-auto rounded-xl border border-border bg-black/60 p-3 font-mono text-xs text-zinc-300"
      >
        {lines.length === 0 ? <span className="text-zinc-600">waiting for build output…</span> : null}
        {lines.map((line, index) => (
          <div key={index}>{line}</div>
        ))}
      </div>
    </div>
  )
}
