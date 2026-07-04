const checklist = [
  "Mission objectives defined",
  "Constraints identified",
  "Risks assessed",
  "Dependencies resolved",
  "Stakeholders assigned",
  "Artifacts reviewed",
  "Validation passed",
]

import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"

export function ExecutionReadiness() {
  return (
    <section>
      <SectionHeader title="Execution Readiness" />

      <div className="rounded-[12px] border border-[#EAEFF5] bg-white p-5">
        <div className="space-y-2.5">
          {checklist.map((item) => (
            <div key={item} className="flex items-center gap-3">
              <div aria-hidden="true" className="flex h-5 w-5 shrink-0 items-center justify-center rounded-[5px] border-2 border-[#D1D9E6] bg-[#F8FAFC]" />
              <span className="text-[0.82rem] text-[#9CA3AF]">{item}</span>
            </div>
          ))}
        </div>
        <div aria-hidden="true" className="mt-4 flex items-center gap-2">
          <div className="h-1.5 flex-1 rounded-full bg-[#F0F4F8]" />
          <span className="text-[0.72rem] font-medium text-[#B0B7C3]">0 / 7</span>
        </div>
      </div>
    </section>
  )
}
