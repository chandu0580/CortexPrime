const constraintGroups = [
  { label: "Business Constraints",   items: 3 },
  { label: "Technical Constraints",  items: 3 },
  { label: "Compliance Constraints", items: 3 },
  { label: "Operational Constraints", items: 3 },
]

import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"

export function ConstraintsPanel() {
  return (
    <section>
      <SectionHeader title="Constraints" />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {constraintGroups.map((group) => (
          <div key={group.label} className="rounded-[10px] border border-[#EAEFF5] bg-white p-4">
            <p className="mb-2.5 text-[0.72rem] font-semibold uppercase tracking-wider text-[#9CA3AF]">
              {group.label}
            </p>
            <div className="space-y-2">
              {Array.from({ length: group.items }).map((_, i) => (
                <div key={i} className="flex items-center gap-2">
                  <div aria-hidden="true" className="h-3 w-3 shrink-0 rounded-[3px] border border-[#D1D9E6]" />
                  <div aria-hidden="true" className="h-3 w-full rounded bg-[#F0F4F8]" />
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
