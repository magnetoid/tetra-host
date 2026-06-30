import type { ButtonHTMLAttributes } from "react"
import type { IconDefinition } from "@fortawesome/fontawesome-svg-core"
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center rounded-lg font-medium transition disabled:cursor-not-allowed disabled:opacity-60",
  {
    variants: {
      variant: {
        primary: "bg-white text-black hover:bg-zinc-200",
        secondary: "border border-border text-zinc-200 hover:bg-zinc-900",
        danger: "border border-red-900 text-red-300 hover:bg-red-950",
        ghost: "text-zinc-400 hover:bg-zinc-900",
      },
      size: {
        sm: "px-2.5 py-1 text-xs gap-1.5",
        md: "px-3 py-2 text-sm gap-2",
      },
    },
    defaultVariants: {
      variant: "secondary",
      size: "md",
    },
  },
)

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof buttonVariants> & {
    icon?: IconDefinition
  }

/** The one button. Consistent radius, transitions, disabled state, and optional leading icon. */
export function Button({
  variant,
  size,
  icon,
  className,
  children,
  ...props
}: ButtonProps) {
  return (
    <button className={cn(buttonVariants({ variant, size }), className)} {...props}>
      {icon ? <FontAwesomeIcon icon={icon} className="h-3.5 w-3.5" fixedWidth /> : null}
      {children}
    </button>
  )
}

export { buttonVariants }
