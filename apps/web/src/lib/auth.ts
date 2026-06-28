import { redirect } from "next/navigation"

import { fetchBackend } from "@/lib/api"
import { getSessionToken } from "@/lib/session"
import type { AdminRecord } from "@/lib/types"

export type ConsoleSession = {
  token: string
  admin: AdminRecord
}

export async function requireConsoleSession(nextPath?: string): Promise<ConsoleSession> {
  const token = await getSessionToken()
  if (!token) {
    redirect(nextPath ? `/auth/login?next=${encodeURIComponent(nextPath)}` : "/auth/login")
  }

  try {
    const admin = await fetchBackend<AdminRecord>("/auth/me", { token })
    return { token, admin }
  } catch {
    redirect(nextPath ? `/auth/login?next=${encodeURIComponent(nextPath)}` : "/auth/login")
  }
}
