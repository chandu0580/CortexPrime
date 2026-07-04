import { cn } from "@/utils/cn"
import type { StatusTone } from "@/components/dashboard/data"

export const toneStyles: Record<StatusTone, string> = {
  running:   "bg-[#ECFBF4] text-[#2F9F77] ring-[#D6F0E5]",
  healthy:   "bg-[#ECFBF4] text-[#2F9F77] ring-[#D6F0E5]",
  warning:   "bg-[#FFFBEB] text-[#B45309] ring-[#FDECC8]",
  critical:  "bg-[#FEF2F2] text-[#B91C1C] ring-[#FBD5D5]",
  idle:      "bg-[#F8FAFC] text-[#6B7280] ring-[#E5E7EB]",
  info:      "bg-[#F8FAFC] text-[#374151] ring-[#E5E7EB]",
  completed: "bg-[#ECFBF4] text-[#2F9F77] ring-[#D6F0E5]",
}

export const toneDot: Record<StatusTone, string> = {
  running:   "bg-[#38B88A]",
  healthy:   "bg-[#38B88A]",
  warning:   "bg-[#F59E0B]",
  critical:  "bg-[#EF4444]",
  idle:      "bg-[#9CA3AF]",
  info:      "bg-[#6B7280]",
  completed: "bg-[#38B88A]",
}

export function Badge({ tone, children }: { tone: StatusTone; children: React.ReactNode }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-[3px] text-[0.73rem] font-semibold ring-1", toneStyles[tone])}>
      <span className={cn("h-1.5 w-1.5 rounded-full", toneDot[tone])} />
      {children}
    </span>
  )
}
