import { Card, CardHeader } from "@/components/ui/card"
import type { AppMount } from "@/lib/types"

/** An engine app's volumes and mounts: which service mounts what, and where. */
export function AppVolumes({ mounts }: { mounts: AppMount[] }) {
  return (
    <Card>
      <CardHeader title="Volumes" action={mounts.length ? `${mounts.length} mounts` : undefined} />
      {mounts.length === 0 ? (
        <p className="mt-4 text-sm text-muted-foreground">
          This app has no volumes, so nothing it writes survives a redeploy.
        </p>
      ) : (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs uppercase tracking-wider text-muted-foreground">
                <th className="py-2 pr-4 font-medium">Service</th>
                <th className="py-2 pr-4 font-medium">Volume</th>
                <th className="py-2 pr-4 font-medium">Mounted at</th>
                <th className="py-2 font-medium">Access</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {mounts.map((mount) => (
                <tr key={`${mount.service}:${mount.destination}`}>
                  <td className="py-2 pr-4">{mount.service || "—"}</td>
                  <td className="py-2 pr-4 font-mono text-xs">
                    {mount.name || <span className="text-muted-foreground">{mount.type} mount</span>}
                  </td>
                  <td className="py-2 pr-4 font-mono text-xs">{mount.destination}</td>
                  <td className="py-2 text-xs text-muted-foreground">
                    {mount.read_only ? "read-only" : "read-write"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}
