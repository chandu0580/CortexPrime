import { Activity } from "lucide-react"

export function ActivityRail() {
  return (
    <div className="flex h-[60px] items-center gap-3 border-t border-[#EAEFF5] bg-white px-5">
      <Activity className="h-4 w-4 text-[#D1D5DB]" />
      <span className="text-[0.78rem] text-[#B0B7C3]">No activity</span>
    </div>
  )
}
