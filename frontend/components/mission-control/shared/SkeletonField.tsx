import { memo } from "react"
import { cn } from "@/utils/cn"

interface SkeletonFieldProps {
  label: string
  width?: string
}

export const SkeletonField = memo(function SkeletonField({ label, width = "w-full" }: SkeletonFieldProps) {
  return (
    <div>
      <p className="mb-1 text-[0.7rem] font-medium uppercase tracking-wider text-[#9CA3AF]">
        {label}
      </p>
      <div aria-hidden="true" className={cn("h-4 rounded bg-[#F0F4F8]", width)} />
    </div>
  )
})
SkeletonField.displayName = "SkeletonField"
