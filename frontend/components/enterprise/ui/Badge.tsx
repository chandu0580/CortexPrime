import { cn } from "@/utils/cn"
import type { ReactNode } from "react"

type BadgeVariant = "default" | "success" | "warning" | "danger" | "info"

export function Badge({
  children,
  variant = "default",
  className,
}: {
  children: ReactNode
  variant?: BadgeVariant
  className?: string
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium",
        variant === "default" && "bg-[var(--surface-raised)] text-[var(--text-muted)]",
        variant === "success" && "bg-[var(--success)]/10 text-[var(--success)]",
        variant === "warning" && "bg-yellow-500/10 text-yellow-500",
        variant === "danger" && "bg-[var(--danger)]/10 text-[var(--danger)]",
        variant === "info" && "bg-[var(--accent-muted)] text-[var(--accent)]",
        className,
      )}
    >
      {children}
    </span>
  )
}
