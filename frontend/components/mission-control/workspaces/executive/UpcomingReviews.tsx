"use client"

import { useWorkspaceExecutive } from "@/hooks"
import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"
import { EmptyState } from "@/components/mission-control/shared/EmptyState"

export function UpcomingReviews() {
  const { data } = useWorkspaceExecutive()

  const totalMissions = data?.totalMissions ?? 0

  if (totalMissions === 0) {
    return (
      <section>
        <SectionHeader title="Upcoming Reviews" />
        <EmptyState
          variant="shell"
          icon={
            <svg className="h-5 w-5 text-[#D1D5DB]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
            </svg>
          }
          title="No scheduled reviews"
          description="Reviews will be scheduled as missions progress through their lifecycle"
        />
      </section>
    )
  }

  return (
    <section>
      <SectionHeader title="Upcoming Reviews" />

      <div className="rounded-[12px] border border-[#EAEFF5] bg-white p-5">
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-[0.84rem] font-medium text-[#111827]">Missions requiring review</span>
            <span className="text-[0.9rem] font-bold text-[#38B88A]">{totalMissions}</span>
          </div>
          <div className="flex items-center justify-between text-[0.74rem] text-[#6B7280]">
            <span>Completed</span>
            <span className="font-semibold text-[#38B88A]">{data?.completedMissions ?? 0}</span>
          </div>
          <div className="flex items-center justify-between text-[0.74rem] text-[#6B7280]">
            <span>Failed</span>
            <span className="font-semibold text-[#EF4444]">{data?.failedMissions ?? 0}</span>
          </div>
        </div>
      </div>
    </section>
  )
}
