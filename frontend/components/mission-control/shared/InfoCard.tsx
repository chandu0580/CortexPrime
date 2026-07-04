import { memo, type ReactNode } from "react"

import { cn } from "@/utils/cn"

interface InfoCardProps {
  label?: string
  children?: ReactNode
  className?: string
  icon?: ReactNode
  skeletonWidth?: string
}

export const InfoCard = memo(function InfoCard({ label, children, className, icon, skeletonWidth = "w-full" }: InfoCardProps) {
  return (
    <div className={cn("rounded-[10px] border border-[#EAEFF5] bg-white p-4", className)}>
      {icon && (
        <div aria-hidden="true" className="mb-2 flex items-center justify-between">
          <span className="text-[0.8rem] text-[#9CA3AF]">{icon}</span>
        </div>
      )}
      {label && (
        <p className="mb-2 text-[0.7rem] font-medium uppercase tracking-wider text-[#9CA3AF]">
          {label}
        </p>
      )}
      {children || <div aria-hidden="true" className={cn("h-6 rounded bg-[#F0F4F8]", skeletonWidth)} />}
    </div>
  )
})
InfoCard.displayName = "InfoCard"
