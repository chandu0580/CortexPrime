const signalDomains = [
  { label: "Operational",  icon: "⚙" },
  { label: "Financial",    icon: "$" },
  { label: "Compliance",   icon: "⚖" },
  { label: "Security",     icon: "🔒" },
  { label: "Customer",     icon: "☆" },
  { label: "AI",           icon: "◆" },
]

import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"

export function EnterpriseSignals() {
  return (
    <section>
      <SectionHeader title="Enterprise Signals" />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {signalDomains.map((domain) => (
          <div
            key={domain.label}
            className="rounded-[10px] border border-[#EAEFF5] bg-white p-4 text-center"
          >
            <div aria-hidden="true" className="mx-auto mb-1.5 flex h-8 w-8 items-center justify-center rounded-full bg-[#F0F4F8] text-[0.8rem] text-[#9CA3AF]">
              {domain.icon}
            </div>
            <p className="text-[0.78rem] font-medium text-[#111827]">{domain.label}</p>
            <div className="mx-auto mt-2 flex items-center gap-1">
              <div aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-[#D1D5DB]" />
              <span className="text-[0.65rem] text-[#B0B7C3]">No signal</span>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
