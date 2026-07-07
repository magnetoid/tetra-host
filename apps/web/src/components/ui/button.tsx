import type { ButtonHTMLAttributes } from "react"
import type { IconDefinition } from "@fortawesome/fontawesome-svg-core"
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center rounded-lg font-medium transition-all duration-150 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60 disabled:active:scale-100",
  {
    variants: {
      variant: {
        primary: "bg-foreground text-background hover:bg-foreground/90",
        secondary: "border border-border hover:bg-accent",
        danger: "border border-status-err/25 text-status-err hover:bg-status-err/10",
        ghost: "text-muted-foreground hover:bg-accent hover:text-foreground",
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
