import type { ButtonHTMLAttributes } from "react"
import type { IconDefinition } from "@fortawesome/fontawesome-svg-core"
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

/**
 * The one button — shadcn New York, Tetra violet brand. Variant names are
 * back-compatible (primary/secondary/danger/ghost) and extended with the
 * canonical shadcn set (default/destructive/outline/link) so both styles read.
 */
const buttonVariants = cva(
  "inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium outline-none transition-colors focus-visible:ring-[3px] focus-visible:ring-ring/40 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        // Brand primary — violet solid (the one prominent action)
        primary: "bg-primary text-primary-foreground shadow-sm hover:bg-primary/90",
        default: "bg-primary text-primary-foreground shadow-sm hover:bg-primary/90",
        // Quiet outline — the workhorse secondary
        secondary:
          "border border-border bg-transparent shadow-sm hover:bg-accent hover:text-accent-foreground",
        outline:
          "border border-border bg-transparent shadow-sm hover:bg-accent hover:text-accent-foreground",
        // Filled neutral
        muted: "bg-secondary text-secondary-foreground shadow-sm hover:bg-secondary/80",
        // Destructive — subtle by default (back-compat), solid via `destructive`
        danger:
          "border border-destructive/30 text-destructive shadow-sm hover:bg-destructive/10",
        destructive:
          "bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        sm: "h-8 gap-1.5 rounded-md px-3 text-xs",
        md: "h-9 px-4 py-2",
        lg: "h-10 rounded-md px-6",
        icon: "size-9",
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
    /** Render as the child element (e.g. a Next <Link>) instead of a <button>. */
    asChild?: boolean
  }

export function Button({
  variant,
  size,
  icon,
  asChild = false,
  className,
  children,
  ...props
}: ButtonProps) {
  // Slot requires a single child, so when `asChild` the caller composes its own
  // content (icon included); we only inject the icon for the plain <button>.
  const Comp = asChild ? Slot : "button"
  return (
    <Comp className={cn(buttonVariants({ variant, size }), className)} {...props}>
      {!asChild && icon ? <FontAwesomeIcon icon={icon} className="h-3.5 w-3.5" fixedWidth /> : null}
      {children}
    </Comp>
  )
}

export { buttonVariants }
