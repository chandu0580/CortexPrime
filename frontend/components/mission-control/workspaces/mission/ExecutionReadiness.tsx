"use client"

import { useActiveMissions, useMissionEvents } from "@/hooks"
import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"

export function ExecutionReadiness() {
  const { data: activeMissions, isLoading } = useActiveMissions()
  const { data: events } = useMissionEvents()

  const hasActive = (activeMissions?.length ?? 0) > 0
  const hasEvents = (events?.length ?? 0) > 0
  const eventCount = events?.length ?? 0

  const checklist = [
    { label: "Mission objectives defined", met: hasActive },
    { label: "Constraints identified", met: hasActive },
    { label: "Risks assessed", met: hasActive },
    { label: "Dependencies resolved", met: hasActive },
    { label: "Agents assigned", met: hasActive },
    { label: "Events recorded", met: hasEvents },
    { label: "Execution active", met: hasActive },
  ]

  const completedCount = checklist.filter((c) => c.met).length
  const totalCount = checklist.length

  return (
    <section>
      <SectionHeader title="Execution Readiness" />

      <div className="rounded-[12px] border border-[#EAEFF5] bg-white p-5">
        <div className="space-y-2.5">
          {checklist.map((item) => (
            <div key={item.label} className="flex items-center gap-3">
              <div
                className="flex h-5 w-5 shrink-0 items-center justify-center rounded-[5px]"
                style={{
                  backgroundColor: item.met ? "#ECFBF4" : "#F8FAFC",
                  border: item.met ? "none" : "2px solid #D1D9E6",
                }}
              >
                {item.met && (
                  <svg className="h-3 w-3 text-[#38B88A]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                  </svg>
                )}
              </div>
              <span className="text-[0.82rem]" style={{ color: item.met ? "#111827" : "#9CA3AF" }}>
                {item.label}
              </span>
            </div>
          ))}
        </div>
        <div className="mt-4 flex items-center gap-2">
          <div className="h-1.5 flex-1 rounded-full bg-[#F0F4F8]">
            <div
              className="h-full rounded-full bg-[#38B88A] transition-all duration-500"
              style={{ width: `${(completedCount / totalCount) * 100}%` }}
            />
          </div>
          <span className="text-[0.72rem] font-medium" style={{ color: completedCount === totalCount ? "#38B88A" : "#B0B7C3" }}>
            {completedCount} / {totalCount}
          </span>
        </div>
      </div>
    </section>
  )
}
