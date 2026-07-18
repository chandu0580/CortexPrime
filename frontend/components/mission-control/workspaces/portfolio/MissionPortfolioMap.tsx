"use client"

import { useWorkspacePortfolio } from "@/hooks"
import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"
import { EmptyState } from "@/components/mission-control/shared/EmptyState"

export function MissionPortfolioMap() {
  const { data } = useWorkspacePortfolio()

  const total = (data?.activeMissions ?? 0) + (data?.completedMissions ?? 0) + (data?.failedMissions ?? 0)

  if (total === 0) {
    return (
      <section>
        <SectionHeader title="Mission Portfolio Map" />
        <EmptyState
          variant="shell"
          icon={
            <svg className="h-5 w-5 text-[#D1D5DB]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" />
            </svg>
          }
          title="No mission portfolio available"
          description="Commission and validate missions to build the portfolio map"
        />
      </section>
    )
  }

  return (
    <section>
      <SectionHeader title="Mission Portfolio Map" />

      <div className="rounded-[12px] border border-[#EAEFF5] bg-white p-5">
        <div className="grid grid-cols-3 gap-4">
          <div className="rounded-[10px] bg-[#ECFBF4] p-4 text-center">
            <p className="text-[1.4rem] font-bold text-[#38B88A]">{data?.activeMissions ?? 0}</p>
            <p className="text-[0.7rem] font-medium text-[#38B88A]">Active</p>
          </div>
          <div className="rounded-[10px] bg-[#EFF6FF] p-4 text-center">
            <p className="text-[1.4rem] font-bold text-[#3B82F6]">{data?.completedMissions ?? 0}</p>
            <p className="text-[0.7rem] font-medium text-[#3B82F6]">Completed</p>
          </div>
          <div className="rounded-[10px] bg-[#FEF2F2] p-4 text-center">
            <p className="text-[1.4rem] font-bold text-[#EF4444]">{data?.failedMissions ?? 0}</p>
            <p className="text-[0.7rem] font-medium text-[#EF4444]">Failed</p>
          </div>
        </div>
        <div className="mt-4 flex items-center justify-between text-[0.72rem] text-[#6B7280]">
          <span>Success rate: {data?.successRate ?? 100}%</span>
          <span>{data?.activeAgents ?? 0} agents</span>
        </div>
      </div>
    </section>
  )
}
