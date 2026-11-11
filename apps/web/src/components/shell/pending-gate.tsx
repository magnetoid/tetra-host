import { APP_NAME } from "@/lib/env"
import type { AdminRecord } from "@/lib/types"

export function PendingGate({ admin }: { admin: AdminRecord }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background px-6 text-center">
      <div className="mb-6 grid h-16 w-16 place-items-center rounded-lg bg-muted text-3xl">
        ⏳
      </div>
      <h1 className="text-2xl font-semibold tracking-tight">Account awaiting approval</h1>
      <p className="mt-3 max-w-sm text-sm text-muted-foreground">
        Your organisation{" "}
        {admin.tenant_name ? (
          <strong className="text-foreground">{admin.tenant_name}</strong>
        ) : (
          "your account"
        )}{" "}
        has been registered and is pending review by a platform administrator.
      </p>
      <p className="mt-2 text-sm text-muted-foreground">
        You will receive access once your account is approved.
      </p>
      <div className="mt-8 rounded-lg border border-border bg-muted p-6 text-left text-sm">
        <div className="font-medium text-foreground">Account details</div>
        <div className="mt-3 space-y-1 text-muted-foreground">
          <div>
            <span className="text-muted-foreground">Email: </span>
            {admin.email}
          </div>
          {admin.tenant_name ? (
            <div>
              <span className="text-muted-foreground">Organisation: </span>
              {admin.tenant_name}
            </div>
          ) : null}
          <div>
            <span className="text-muted-foreground">Status: </span>
            <span className="font-medium capitalize text-status-warn">
              {admin.tenant_status ?? "pending"}
            </span>
          </div>
        </div>
      </div>
      <form action="/api/auth/logout" method="post" className="mt-6">
        <button
          type="submit"
          className="rounded-lg border border-border px-4 py-2 text-sm text-muted-foreground transition hover:bg-accent"
        >
          Sign out
        </button>
      </form>
      <p className="mt-6 text-xs text-muted-foreground">{APP_NAME} · Cloud Industry</p>
    </div>
  )
}
