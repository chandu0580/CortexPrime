import type { ReactNode } from "react"
import { cn } from "@/utils/cn"

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: {
  icon?: ReactNode
  title: string
  description?: string
  action?: ReactNode
  className?: string
}) {
  return (
    <div className={cn("flex flex-col items-center justify-center py-16 text-center", className)}>
      {icon && <div className="mb-4 text-[var(--text-muted)]">{icon}</div>}
      <h3 className="type-heading-sm text-[var(--text-primary)]">{title}</h3>
      {description && <p className="type-body mt-2 max-w-sm text-[var(--text-muted)]">{description}</p>}
      {action && <div className="mt-6">{action}</div>}
    </div>
  )
}
