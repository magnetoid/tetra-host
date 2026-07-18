"use client"

import * as SheetPrimitive from "@radix-ui/react-dialog"
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import type { ComponentProps } from "react"

import { faXmark } from "@/lib/icons"
import { cn } from "@/lib/utils"

const Sheet = SheetPrimitive.Root
const SheetTrigger = SheetPrimitive.Trigger
const SheetClose = SheetPrimitive.Close

const sideClasses = {
  right:
    "inset-y-0 right-0 h-full w-3/4 max-w-sm border-l data-[state=open]:slide-in-from-right data-[state=closed]:slide-out-to-right",
  left:
    "inset-y-0 left-0 h-full w-3/4 max-w-sm border-r data-[state=open]:slide-in-from-left data-[state=closed]:slide-out-to-left",
  top: "inset-x-0 top-0 h-auto border-b data-[state=open]:slide-in-from-top data-[state=closed]:slide-out-to-top",
  bottom:
    "inset-x-0 bottom-0 h-auto border-t data-[state=open]:slide-in-from-bottom data-[state=closed]:slide-out-to-bottom",
} as const

function SheetContent({
  className,
  children,
  side = "right",
  ...props
}: ComponentProps<typeof SheetPrimitive.Content> & { side?: keyof typeof sideClasses }) {
  return (
    <SheetPrimitive.Portal>
      <SheetPrimitive.Overlay className="fixed inset-0 z-50 bg-background/70 backdrop-blur-sm data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=closed]:animate-out data-[state=closed]:fade-out-0" />
      <SheetPrimitive.Content
        className={cn(
          "fixed z-50 flex flex-col gap-4 bg-card p-6 shadow-lg border-border transition ease-in-out data-[state=open]:animate-in data-[state=closed]:animate-out",
          sideClasses[side],
          className,
        )}
        {...props}
      >
        {children}
        <SheetPrimitive.Close
          aria-label="Close"
          className="absolute right-4 top-4 rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        >
          <FontAwesomeIcon icon={faXmark} className="size-4" />
        </SheetPrimitive.Close>
      </SheetPrimitive.Content>
    </SheetPrimitive.Portal>
  )
}

function SheetHeader({ className, ...props }: ComponentProps<"div">) {
  return <div className={cn("flex flex-col gap-1", className)} {...props} />
}

function SheetTitle({ className, ...props }: ComponentProps<typeof SheetPrimitive.Title>) {
  return <SheetPrimitive.Title className={cn("text-lg font-semibold", className)} {...props} />
}

function SheetDescription({
  className,
  ...props
}: ComponentProps<typeof SheetPrimitive.Description>) {
  return (
    <SheetPrimitive.Description className={cn("text-sm text-muted-foreground", className)} {...props} />
  )
}

export {
  Sheet,
  SheetTrigger,
  SheetClose,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
}
