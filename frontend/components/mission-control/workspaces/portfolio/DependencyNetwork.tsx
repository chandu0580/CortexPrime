"use client"

import { useWorkspacePortfolio } from "@/hooks"
import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"
import { EmptyState } from "@/components/mission-control/shared/EmptyState"

export function DependencyNetwork() {
  const { data } = useWorkspacePortfolio()

  const total = (data?.activeMissions ?? 0) + (data?.completedMissions ?? 0) + (data?.failedMissions ?? 0)

  if (total < 2) {
    return (
      <section>
        <SectionHeader title="Dependency Network" />
        <EmptyState
          variant="shell"
          icon={
            <svg className="h-5 w-5 text-[#D1D5DB]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m13.35-.622l1.757-1.757a4.5 4.5 0 00-6.364-6.364l-4.5 4.5a4.5 4.5 0 001.242 7.244" />
            </svg>
          }
          title="No dependency network"
          description="Cross-mission dependencies will appear as the portfolio grows"
        />
      </section>
    )
  }

  return (
    <section>
      <SectionHeader title="Dependency Network" />

      <div className="rounded-[12px] border border-[#EAEFF5] bg-white p-5">
        <div className="flex items-center justify-around">
          <div className="text-center">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#ECFBF4] mx-auto">
              <span className="text-[0.8rem] font-bold text-[#38B88A]">{data?.activeMissions ?? 0}</span>
            </div>
            <p className="mt-1 text-[0.68rem] text-[#6B7280]">Active</p>
          </div>
          <div className="h-px w-16 bg-[#D1D9E6]" />
          <div className="text-center">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#EFF6FF] mx-auto">
              <span className="text-[0.8rem] font-bold text-[#3B82F6]">{data?.completedMissions ?? 0}</span>
            </div>
            <p className="mt-1 text-[0.68rem] text-[#6B7280]">Completed</p>
          </div>
          <div className="h-px w-16 bg-[#D1D9E6]" />
          <div className="text-center">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#ECFBF4] mx-auto">
              <span className="text-[0.8rem] font-bold text-[#38B88A]">{data?.activeAgents ?? 0}</span>
            </div>
            <p className="mt-1 text-[0.68rem] text-[#6B7280]">Agents</p>
          </div>
        </div>
        <p className="mt-4 text-center text-[0.7rem] text-[#9CA3AF]">{total} total missions in portfolio</p>
      </div>
    </section>
  )
}
