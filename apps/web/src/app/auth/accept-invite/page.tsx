import Link from "next/link"

import { AcceptInviteForm } from "@/components/auth/accept-invite-form"
import { TetraWordmark } from "@/components/brand/tetra-wordmark"
import { fetchBackend } from "@/lib/api"
import type { InvitePreview } from "@/lib/types"

type AcceptInvitePageProps = {
  searchParams: Promise<{ token?: string }>
}

export default async function AcceptInvitePage({ searchParams }: AcceptInvitePageProps) {
  const { token } = await searchParams

  const preview = token
    ? await fetchBackend<InvitePreview>("/auth/invite", {
        searchParams: { token },
      }).catch(() => null)
    : null

  return (
    <div className="grid min-h-screen place-items-center bg-background p-6">
      <div className="w-full max-w-md">
        <Link href="/" className="inline-block">
          <TetraWordmark />
        </Link>

        {preview ? (
          <div className="mt-8">
            <h1 className="font-display text-2xl font-semibold">
              Join {preview.tenant_name || "the team"}
            </h1>
            <p className="mt-2 text-sm text-muted-foreground">
              You&apos;ve been invited as{" "}
              <span className="font-medium text-foreground">{preview.role}</span>. Set your name and
              a password to create your account.
            </p>
            <AcceptInviteForm token={token as string} email={preview.email} />
          </div>
        ) : (
          <div className="mt-8 rounded-2xl border border-border bg-muted p-6">
            <h1 className="font-display text-xl font-semibold">This invite isn&apos;t valid</h1>
            <p className="mt-2 text-sm text-muted-foreground">
              The link may have expired, already been used, or been revoked. Ask your team owner to
              send a fresh invite.
            </p>
            <Link
              href="/auth/login"
              className="mt-4 inline-block text-sm text-primary hover:underline"
            >
              Go to sign in
            </Link>
          </div>
        )}
      </div>
    </div>
  )
}
