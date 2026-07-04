import { cn } from "@/utils/cn"

const slots = [
  { label: "Portfolio Confidence", width: "w-[120px]" },
  { label: "Active Interventions", width: "w-[100px]" },
  { label: "Pending Approvals",    width: "w-[90px]" },
  { label: "Current Time",         width: "w-[80px]" },
]

export function PersistentContextBar() {
  return (
    <div className="flex h-9 items-center gap-4 border-b border-[#EAEFF5] bg-white px-5">
      <span className="text-[0.68rem] font-semibold uppercase tracking-wider text-[#9CA3AF]">
        Context
      </span>
      {slots.map((slot) => (
        <div key={slot.label} className="flex items-center gap-2">
          <div className={cn("h-3 rounded bg-[#F0F4F8]", slot.width)} />
          <span className="text-[0.7rem] text-[#B0B7C3]">{slot.label}</span>
        </div>
      ))}
      <div className="flex-1" />
      <div className="flex items-center gap-1.5">
        <span className="h-1.5 w-1.5 rounded-full bg-[#D1D5DB]" />
        <span className="text-[0.7rem] text-[#9CA3AF]">Operational</span>
      </div>
    </div>
  )
}
