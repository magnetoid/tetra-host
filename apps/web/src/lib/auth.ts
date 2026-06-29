import { redirect } from "next/navigation"

import { fetchBackend } from "@/lib/api"
import { getSessionToken } from "@/lib/session"
import type { AdminRecord } from "@/lib/types"

export type ConsoleSession = {
  token: string
  admin: AdminRecord
}

/** Resolve the session if the cookie is present AND valid, else null. Never redirects. */
export async function getConsoleSession(): Promise<ConsoleSession | null> {
  const token = await getSessionToken()
  if (!token) {
    return null
  }
  try {
    const admin = await fetchBackend<AdminRecord>("/auth/me", { token })
    return { token, admin }
  } catch {
    return null
  }
}

export async function requireConsoleSession(nextPath?: string): Promise<ConsoleSession> {
  const session = await getConsoleSession()
  if (!session) {
    redirect(nextPath ? `/auth/login?next=${encodeURIComponent(nextPath)}` : "/auth/login")
  }
  return session
}
