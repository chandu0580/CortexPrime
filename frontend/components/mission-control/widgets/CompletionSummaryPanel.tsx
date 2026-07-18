"use client"

import { useMissions, useWorkspaceMission } from "@/hooks"
import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"
import { InfoCard } from "@/components/mission-control/shared/InfoCard"
import { EmptyState } from "@/components/mission-control/shared/EmptyState"

export function CompletionSummaryPanel() {
  const { data: missions, isLoading } = useMissions()
  const { data: wsData } = useWorkspaceMission()

  const allMissions = missions ?? []
  const completed = allMissions.filter((m) => m.status === "completed")
  const failed = allMissions.filter((m) => m.status === "failed")
  const active = allMissions.filter((m) => m.status === "running")

  const totalCount = allMissions.length
  const completedCount = completed.length
  const failedCount = failed.length
  const activeCount = active.length
  const successRate = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 100

  if (totalCount === 0 && !isLoading) {
    return (
      <section>
        <SectionHeader title="Completion Summary" />
        <EmptyState
          variant="shell"
          icon={
            <svg className="h-5 w-5 text-[#D1D5DB]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          }
          title="No mission data available"
          description="Start a mission to see completion summary"
        />
      </section>
    )
  }

  return (
    <section>
      <SectionHeader title="Completion Summary" />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <InfoCard label="Total Missions">
          <p className="text-[1.1rem] font-bold text-[#111827]">{totalCount}</p>
        </InfoCard>
        <InfoCard label="Completed">
          <p className="text-[1.1rem] font-bold text-[#38B88A]">{completedCount}</p>
        </InfoCard>
        <InfoCard label="Failed">
          <p className="text-[1.1rem] font-bold text-[#EF4444]">{failedCount}</p>
        </InfoCard>
        <InfoCard label="Success Rate">
          <p className="text-[1.1rem] font-bold" style={{ color: successRate >= 90 ? "#38B88A" : successRate >= 50 ? "#F59E0B" : "#EF4444" }}>
            {successRate}%
          </p>
        </InfoCard>
      </div>

      {activeCount > 0 && (
        <div className="mt-3 rounded-[10px] border border-[#E8EDF3] bg-[#FAFCFB] px-4 py-3">
          <div className="flex items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-[#3B82F6] animate-pulse" />
            <span className="text-[0.78rem] text-[#6B7280]">{activeCount} mission{activeCount > 1 ? "s" : ""} in progress</span>
          </div>
        </div>
      )}

      {totalCount > 0 && (
        <div className="mt-3 h-2 w-full rounded-full bg-[#F0F4F8] overflow-hidden">
          <div className="h-full flex">
            <div
              className="bg-[#38B88A] h-full transition-all duration-500"
              style={{ width: `${totalCount > 0 ? (completedCount / totalCount) * 100 : 0}%` }}
            />
            <div
              className="bg-[#EF4444] h-full transition-all duration-500"
              style={{ width: `${totalCount > 0 ? (failedCount / totalCount) * 100 : 0}%` }}
            />
          </div>
        </div>
      )}
    </section>
  )
}
