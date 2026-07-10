"use client"

import { useRouter } from "next/navigation"
import { useState } from "react"

import { AlertBanner } from "@/components/ui/alert-banner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { faArrowsRotate, faPlus } from "@/lib/icons"
import type { BadgeVariant } from "@/components/ui/badge"
import type { InviteCreateResult, TeamResponse } from "@/lib/types"
import { formatRelativeLabel } from "@/lib/utils"

const INPUT_CLASS =
  "rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/25"

function roleVariant(role: string): BadgeVariant {
  if (role === "owner") return "success"
  if (role === "platform_admin") return "warning"
  if (role === "admin") return "default"
  return "secondary"
}

export function TeamManager({
  team,
  currentRole,
  currentAdminId,
}: {
  team: TeamResponse
  currentRole: string
  currentAdminId: string
}) {
  const router = useRouter()
  const canManage = currentRole === "owner" || currentRole === "platform_admin"

  const [email, setEmail] = useState("")
  const [role, setRole] = useState("member")
  const [pending, setPending] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  // The share link is returned exactly once, at creation — surfaced here to copy.
  const [freshLink, setFreshLink] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  async function invite(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setPending("invite")
    setError(null)
    setFreshLink(null)
    try {
      const response = await fetch("/api/proxy/team/invites", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, role }),
      })
      const payload = (await response.json().catch(() => ({}))) as InviteCreateResult & {
        detail?: string
      }
      if (!response.ok) {
        setError(payload.detail ?? "Could not create the invite.")
        return
      }
      setFreshLink(`${window.location.origin}${payload.accept_url}`)
      setEmail("")
      router.refresh()
    } catch {
      setError("Unable to reach the control plane.")
    } finally {
      setPending(null)
    }
  }

  async function act(key: string, url: string, init: RequestInit) {
    setPending(key)
    setError(null)
    try {
      const response = await fetch(url, init)
      if (!response.ok) {
        const payload = (await response.json().catch(() => ({}))) as { detail?: string }
        setError(payload.detail ?? "Action failed.")
        return
      }
      router.refresh()
    } catch {
      setError("Unable to reach the control plane.")
    } finally {
      setPending(null)
    }
  }

  const changeRole = (id: string, next: string) =>
    act(`role:${id}`, `/api/proxy/team/members/${id}/role`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role: next }),
    })

  const removeMember = (id: string) =>
    act(`remove:${id}`, `/api/proxy/team/members/${id}`, { method: "DELETE" })

  const revokeInvite = (id: string) =>
    act(`revoke:${id}`, `/api/proxy/team/invites/${id}`, { method: "DELETE" })

  async function copy(link: string) {
    try {
      await navigator.clipboard.writeText(link)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      /* clipboard blocked — the link is visible to copy manually */
    }
  }

  return (
    <div className="space-y-6">
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}

      {canManage ? (
        <form onSubmit={invite} className="rounded-2xl border border-border bg-muted p-4">
          <div className="flex flex-wrap items-end gap-3">
            <label className="block flex-1 text-sm">
              <span className="mb-2 block text-muted-foreground">Invite by email</span>
              <input
                aria-label="Invite email"
                type="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="teammate@company.com"
                className={`${INPUT_CLASS} w-full`}
              />
            </label>
            <label className="block text-sm">
              <span className="mb-2 block text-muted-foreground">Role</span>
              <select
                aria-label="Invite role"
                value={role}
                onChange={(event) => setRole(event.target.value)}
                className={INPUT_CLASS}
              >
                <option value="member">Member</option>
                <option value="admin">Admin</option>
              </select>
            </label>
            <Button type="submit" icon={faPlus} disabled={pending !== null}>
              {pending === "invite" ? "…" : "Create invite"}
            </Button>
          </div>

          {freshLink ? (
            <div className="mt-4 rounded-xl border border-primary/30 bg-background p-3">
              <div className="text-xs text-muted-foreground">
                Share this link with your teammate — it&apos;s shown once and works without email.
              </div>
              <div className="mt-2 flex items-center gap-2">
                <input
                  readOnly
                  aria-label="Invite link"
                  value={freshLink}
                  className={`${INPUT_CLASS} w-full font-mono text-xs`}
                  onFocus={(event) => event.currentTarget.select()}
                />
                <Button type="button" size="sm" onClick={() => copy(freshLink)}>
                  {copied ? "Copied" : "Copy"}
                </Button>
              </div>
            </div>
          ) : null}
        </form>
      ) : null}

      {/* Members */}
      <div className="overflow-hidden rounded-2xl border border-border">
        <div className="border-b border-border bg-background px-4 py-3 text-sm font-medium">
          Members
        </div>
        <div className="divide-y divide-border">
          {team.members.map((member) => {
            const isSelf = member.id === currentAdminId
            const manageable =
              canManage && !isSelf && member.role !== "owner" && member.role !== "platform_admin"
            return (
              <div
                key={member.id}
                className="flex flex-wrap items-center justify-between gap-3 bg-background px-4 py-3"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm font-medium">{member.full_name}</span>
                    <Badge variant={roleVariant(member.role)}>{member.role}</Badge>
                    {isSelf ? (
                      <span className="text-xs text-muted-foreground">you</span>
                    ) : null}
                    {!member.is_active ? (
                      <Badge variant="outline">deactivated</Badge>
                    ) : null}
                  </div>
                  <div className="truncate font-mono text-xs text-muted-foreground">
                    {member.email}
                    {member.last_login_at
                      ? ` · last seen ${formatRelativeLabel(member.last_login_at)}`
                      : " · never signed in"}
                  </div>
                </div>
                {manageable && member.is_active ? (
                  <div className="flex items-center gap-2">
                    <Button
                      size="sm"
                      icon={faArrowsRotate}
                      disabled={pending !== null}
                      onClick={() =>
                        changeRole(member.id, member.role === "admin" ? "member" : "admin")
                      }
                    >
                      {pending === `role:${member.id}`
                        ? "…"
                        : member.role === "admin"
                          ? "Make member"
                          : "Make admin"}
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={pending !== null}
                      onClick={() => removeMember(member.id)}
                    >
                      {pending === `remove:${member.id}` ? "…" : "Remove"}
                    </Button>
                  </div>
                ) : null}
              </div>
            )
          })}
        </div>
      </div>

      {/* Pending invites */}
      {team.invites.length > 0 ? (
        <div className="overflow-hidden rounded-2xl border border-border">
          <div className="border-b border-border bg-background px-4 py-3 text-sm font-medium">
            Pending invites
          </div>
          <div className="divide-y divide-border">
            {team.invites.map((inv) => (
              <div
                key={inv.id}
                className="flex flex-wrap items-center justify-between gap-3 bg-background px-4 py-3"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="truncate font-mono text-sm">{inv.email}</span>
                    <Badge variant={roleVariant(inv.role)}>{inv.role}</Badge>
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {inv.expires_at ? `expires ${formatRelativeLabel(inv.expires_at)}` : "pending"}
                  </div>
                </div>
                {canManage ? (
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={pending !== null}
                    onClick={() => revokeInvite(inv.id)}
                  >
                    {pending === `revoke:${inv.id}` ? "…" : "Revoke"}
                  </Button>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  )
}
