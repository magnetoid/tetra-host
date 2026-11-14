import { cn } from "@/lib/utils"

/**
 * Slides its content open and shut by animating the grid row from 0fr to 1fr, so no
 * height has to be measured. Closed content is `inert`: out of the tab order and
 * hidden from assistive tech. It only moves once the viewer has toggled something
 * (`html[data-nav-animate]`, see globals.css), so state restored on page load
 * appears in place instead of sliding shut; no motion under prefers-reduced-motion.
 */
export function Collapsible({
  open,
  id,
  children,
  className,
}: {
  open: boolean
  id?: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <div
      id={id}
      className={cn(
        "nav-collapsible grid",
        open ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0",
        className,
      )}
      inert={!open}
    >
      <div className="min-h-0 overflow-hidden">{children}</div>
    </div>
  )
}
