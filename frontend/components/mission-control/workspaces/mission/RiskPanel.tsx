const riskColumns = ["Risk", "Impact", "Likelihood", "Mitigation"]

import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"

export function RiskPanel() {
  return (
    <section>
      <SectionHeader title="Risk Assessment" />

      <div className="overflow-hidden rounded-[12px] border border-[#EAEFF5] bg-white">
        {/* Header row */}
        <div className="grid grid-cols-4 border-b border-[#EAEFF5] bg-[#F8FAFC]">
          {riskColumns.map((col) => (
            <div key={col} className="px-4 py-2.5 text-[0.7rem] font-semibold uppercase tracking-wider text-[#9CA3AF]">
              {col}
            </div>
          ))}
        </div>

        {/* Empty rows */}
        {[1, 2, 3].map((row) => (
          <div key={row} className="grid grid-cols-4 border-b border-[#EAEFF5] last:border-b-0">
            {riskColumns.map((col) => (
              <div key={col} className="px-4 py-3">
                <div aria-hidden="true" className="h-4 w-4/5 rounded bg-[#F0F4F8]" />
              </div>
            ))}
          </div>
        ))}
      </div>
    </section>
  )
}
