"use client"

import { useWorkspaceMission } from "@/hooks"
import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"
import { EmptyState } from "@/components/mission-control/shared/EmptyState"

export function DependencyGraph() {
  const { data } = useWorkspaceMission()
  const activeMissions = data?.activeMissions ?? []

  if (activeMissions.length === 0) {
    return (
      <section>
        <SectionHeader title="Mission Dependency Graph" />
        <EmptyState
          variant="shell"
          icon={
            <svg className="h-5 w-5 text-[#D1D5DB]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
            </svg>
          }
          title="No dependencies available"
          description="Dependencies will be resolved during mission planning"
        />
      </section>
    )
  }

  return (
    <section>
      <SectionHeader title="Mission Dependency Graph" />

      <div className="rounded-[12px] border border-[#EAEFF5] bg-white p-5">
        <div className="flex flex-wrap gap-3">
          {activeMissions.map((m, i) => (
            <div key={m.execution_id} className="flex items-center gap-2">
              <div className="rounded-[8px] border border-[#E8EDF3] bg-[#FAFCFB] px-3 py-2">
                <p className="text-[0.72rem] font-medium text-[#374151] truncate max-w-[140px]">{m.goal}</p>
                <p className="text-[0.62rem] text-[#9CA3AF]">{m.status}</p>
              </div>
              {i < activeMissions.length - 1 && (
                <div className="text-[#D1D5DB] text-[0.7rem]">
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
                  </svg>
                </div>
              )}
            </div>
          ))}
        </div>
        {activeMissions.length > 1 && (
          <p className="mt-3 text-[0.7rem] text-[#9CA3AF]">{activeMissions.length} active missions in pipeline</p>
        )}
      </div>
    </section>
  )
}
