"use client"

import { createContext, useContext, useEffect, useState } from "react"

import type { ScopeLabels } from "@/lib/navigation"

type Ctx = { labels: ScopeLabels; setLabels: (next: ScopeLabels) => void }

const ScopeLabelsContext = createContext<Ctx>({ labels: {}, setLabels: () => {} })

/**
 * Human names for the current scope (team, project, app). The URL only carries
 * ids/slugs, so the server component that already fetched the entity renders
 * <SetScopeLabels> and the shell's breadcrumbs and sidebar pick the names up.
 */
export function ScopeLabelsProvider({ team, children }: { team?: string; children: React.ReactNode }) {
  const [labels, setLabels] = useState<ScopeLabels>({})
  return (
    <ScopeLabelsContext.Provider value={{ labels: { ...labels, team: team || labels.team }, setLabels }}>
      {children}
    </ScopeLabelsContext.Provider>
  )
}

export function useScopeLabels(): ScopeLabels {
  return useContext(ScopeLabelsContext).labels
}

export function SetScopeLabels({ project, app }: { project?: string; app?: string }) {
  const { setLabels } = useContext(ScopeLabelsContext)
  useEffect(() => {
    setLabels({ project, app })
    return () => setLabels({})
  }, [project, app, setLabels])
  return null
}
