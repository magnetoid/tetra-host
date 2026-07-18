"use client"

import * as Dialog from "@radix-ui/react-dialog"
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"

import { faXmark } from "@/lib/icons"

type ModalProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: React.ReactNode
  description?: React.ReactNode
  children: React.ReactNode
  footer?: React.ReactNode
  /** Extra classes for the content panel (e.g. a wider max-width). */
  className?: string
}

/**
 * Reusable centered modal dialog on Radix (focus-trap, Esc, backdrop, ARIA).
 * Shares the command-menu's overlay/panel language so modals feel consistent.
 */
export function Modal({
  open,
  onOpenChange,
  title,
  description,
  children,
  footer,
  className,
}: ModalProps) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-background/70 backdrop-blur-sm data-[state=open]:animate-in" />
        <Dialog.Content
          className={[
            "fixed left-1/2 top-1/2 z-50 max-h-[85vh] w-[92vw] max-w-lg -translate-x-1/2 -translate-y-1/2",
            "overflow-hidden rounded-lg border border-border bg-popover shadow-2xl",
            className ?? "",
          ]
            .filter(Boolean)
            .join(" ")}
        >
          <div className="flex items-start justify-between gap-4 border-b border-border p-5">
            <div className="min-w-0">
              <Dialog.Title className="text-lg font-semibold">{title}</Dialog.Title>
              {description ? (
                <Dialog.Description className="mt-1 text-sm text-muted-foreground">
                  {description}
                </Dialog.Description>
              ) : (
                <Dialog.Description className="sr-only">Details</Dialog.Description>
              )}
            </div>
            <Dialog.Close
              aria-label="Close"
              className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            >
              <FontAwesomeIcon icon={faXmark} className="h-4 w-4" />
            </Dialog.Close>
          </div>

          <div className="max-h-[60vh] overflow-y-auto p-5">{children}</div>

          {footer ? (
            <div className="flex items-center justify-end gap-2 border-t border-border p-4">
              {footer}
            </div>
          ) : null}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
