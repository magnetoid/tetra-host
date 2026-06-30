import { APP_NAME } from "@/lib/env"
import type { AdminRecord } from "@/lib/types"

export function PendingGate({ admin }: { admin: AdminRecord }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background px-6 text-center">
      <div className="mb-6 grid h-16 w-16 place-items-center rounded-2xl bg-muted text-3xl">
        ⏳
      </div>
      <h1 className="text-2xl font-semibold tracking-tight">Account awaiting approval</h1>
      <p className="mt-3 max-w-sm text-sm text-zinc-400">
        Your organisation{" "}
        {admin.tenant_name ? (
          <strong className="text-zinc-200">{admin.tenant_name}</strong>
        ) : (
          "your account"
        )}{" "}
        has been registered and is pending review by a platform administrator.
      </p>
      <p className="mt-2 text-sm text-zinc-500">
        You will receive access once your account is approved.
      </p>
      <div className="mt-8 rounded-2xl border border-border bg-muted p-6 text-left text-sm">
        <div className="font-medium text-zinc-300">Account details</div>
        <div className="mt-3 space-y-1 text-zinc-500">
          <div>
            <span className="text-zinc-400">Email: </span>
            {admin.email}
          </div>
          {admin.tenant_name ? (
            <div>
              <span className="text-zinc-400">Organisation: </span>
              {admin.tenant_name}
            </div>
          ) : null}
          <div>
            <span className="text-zinc-400">Status: </span>
            <span className="font-medium capitalize text-yellow-400">
              {admin.tenant_status ?? "pending"}
            </span>
          </div>
        </div>
      </div>
      <form action="/api/auth/logout" method="post" className="mt-6">
        <button
          type="submit"
          className="rounded-lg border border-border px-4 py-2 text-sm text-zinc-400 transition hover:bg-zinc-800"
        >
          Sign out
        </button>
      </form>
      <p className="mt-6 text-xs text-zinc-600">{APP_NAME} · Cloud Industry</p>
    </div>
  )
}
