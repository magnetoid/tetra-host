import type { InputHTMLAttributes } from "react"

import { cn } from "@/lib/utils"

export type InputProps = InputHTMLAttributes<HTMLInputElement>

function Input({ className, type, ...props }: InputProps) {
  return (
    <input
      type={type}
      className={cn(
        "flex h-9 w-full rounded-lg border border-input bg-background px-3 py-1 text-sm text-foreground shadow-sm",
        "placeholder:text-muted-foreground",
        "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "transition",
        className,
      )}
      {...props}
    />
  )
}

export { Input }
