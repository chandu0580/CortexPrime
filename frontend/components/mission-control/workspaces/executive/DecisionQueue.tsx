"use client"

import { useWorkspaceExecutive } from "@/hooks"
import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"
import { EmptyState } from "@/components/mission-control/shared/EmptyState"

export function DecisionQueue() {
  const { data } = useWorkspaceExecutive()

  const queueDepth = data?.queueDepth ?? 0

  if (queueDepth === 0) {
    return (
      <section>
        <SectionHeader title="Decision Queue" />
        <EmptyState
          variant="shell"
          icon={
            <svg className="h-5 w-5 text-[#D1D5DB]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          }
          title="No decisions requiring attention"
          description="Decisions will appear when missions require executive input"
        />
      </section>
    )
  }

  return (
    <section>
      <SectionHeader title="Decision Queue" />
      <div className="rounded-[12px] border border-[#EAEFF5] bg-white p-5">
        <div className="flex items-center justify-between">
          <span className="text-[0.84rem] font-medium text-[#111827]">Pending items in queue</span>
          <span className="text-[1.2rem] font-bold text-[#F59E0B]">{queueDepth}</span>
        </div>
        {data?.currentMission && (
          <p className="mt-2 text-[0.74rem] text-[#6B7280]">
            Current mission: {data.currentMission.goal}
          </p>
        )}
      </div>
    </section>
  )
}
