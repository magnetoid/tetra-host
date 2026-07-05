import type { HTMLAttributes } from "react"

import { cn } from "@/lib/utils"

/** Theme-aware loading placeholder. `bg-foreground/10` reads as a faint tint in both modes. */
export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("animate-pulse rounded-md bg-foreground/10", className)} {...props} />
}
