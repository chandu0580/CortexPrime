import { memo, type ReactNode } from "react"

import GlassPanel from "@/components/ui/GlassPanel"
import { cn } from "@/utils/cn"

interface EmptyStateProps {
  icon: ReactNode
  title: string
  description?: string
  variant?: "shell" | "standalone"
  minHeight?: string
  verticalPadding?: string
}

export const EmptyState = memo(function EmptyState({
  icon,
  title,
  description,
  variant = "standalone",
  minHeight = "min-h-[200px]",
  verticalPadding = "py-12",
}: EmptyStateProps) {
  if (variant === "shell") {
    return (
      <div role="status" className="flex flex-col items-center justify-center rounded-[12px] border border-dashed border-[#D1D9E6] bg-white py-10">
        <div aria-hidden="true" className="mb-2 flex h-10 w-10 items-center justify-center rounded-[10px] bg-[#F8FAFC]">
          {icon}
        </div>
        <p className="text-[0.84rem] font-medium text-[#9CA3AF]">{title}</p>
        {description && <p className="mt-1 text-[0.74rem] text-[#B0B7C3]">{description}</p>}
      </div>
    )
  }

  return (
    <GlassPanel className={cn("flex items-center justify-center", minHeight)} padding={false}>
      <div role="status" className={cn("flex flex-col items-center gap-3 text-center", verticalPadding)}>
        <span aria-hidden="true">{icon}</span>
        <p className="text-base font-medium text-[#9CA3AF]">{title}</p>
        {description && <p className="text-sm text-[#D1D5DB]">{description}</p>}
      </div>
    </GlassPanel>
  )
})
EmptyState.displayName = "EmptyState"
