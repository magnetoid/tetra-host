import { Skeleton } from "@/components/ui/skeleton"

/** Structural loading skeletons that mirror each surface's real layout — shown by
 *  route-segment loading.tsx while server data streams (perceived-speed / no-spinner). */

function HeaderSkeleton() {
  return (
    <div className="space-y-3">
      <Skeleton className="h-3 w-28" />
      <Skeleton className="h-9 w-64 max-w-full" />
      <Skeleton className="h-4 w-[28rem] max-w-full" />
    </div>
  )
}

export function CardSkeleton({ className }: { className?: string }) {
  return <Skeleton className={`h-32 rounded-2xl ${className ?? ""}`} />
}

export function StatRowSkeleton({ count = 5 }: { count?: number }) {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
      {Array.from({ length: count }).map((_, index) => (
        <div key={index} className="rounded-2xl border border-border bg-card p-5">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="mt-3 h-8 w-16" />
          <Skeleton className="mt-2 h-3 w-20" />
        </div>
      ))}
    </div>
  )
}

export function TableSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div className="overflow-hidden rounded-2xl border border-border">
      <div className="border-b border-border bg-muted/40 p-4">
        <Skeleton className="h-4 w-40" />
      </div>
      <div className="divide-y divide-border">
        {Array.from({ length: rows }).map((_, index) => (
          <div key={index} className="flex items-center gap-4 p-4">
            <Skeleton className="h-4 w-1/4" />
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="ml-auto h-6 w-16 rounded-full" />
          </div>
        ))}
      </div>
    </div>
  )
}

export function PageSkeleton({
  variant = "cards",
}: {
  variant?: "cards" | "table" | "dashboard"
}) {
  return (
    <div className="space-y-8">
      <HeaderSkeleton />
      {variant === "dashboard" ? (
        <>
          <StatRowSkeleton />
          <CardSkeleton className="h-72" />
          <div className="grid gap-4 lg:grid-cols-3">
            <CardSkeleton className="h-64" />
            <CardSkeleton className="h-64" />
            <CardSkeleton className="h-64" />
          </div>
        </>
      ) : variant === "table" ? (
        <TableSkeleton />
      ) : (
        <div className="grid gap-4">
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
        </div>
      )}
    </div>
  )
}
