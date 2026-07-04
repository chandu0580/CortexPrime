const sections = ["Lessons", "Patterns", "Recommendations", "Templates"]

import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"

export function PortfolioLearning() {
  return (
    <section>
      <SectionHeader title="Portfolio Learning" />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {sections.map((section) => (
          <div
            key={section}
            className="rounded-[10px] border border-dashed border-[#D1D9E6] bg-white p-4"
          >
            <div aria-hidden="true" className="mb-2 flex h-7 w-7 items-center justify-center rounded-[6px] bg-[#F8FAFC]">
              <div className="h-3 w-3 rounded border border-[#D1D5DB]" />
            </div>
            <p className="text-[0.8rem] font-medium text-[#111827]">{section}</p>
            <p className="mt-1 text-[0.68rem] text-[#B0B7C3]">No entries</p>
          </div>
        ))}
      </div>
    </section>
  )
}
