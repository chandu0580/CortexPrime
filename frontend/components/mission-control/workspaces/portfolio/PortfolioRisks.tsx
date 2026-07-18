"use client"

import { useWorkspacePortfolio } from "@/hooks"
import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"
import { EmptyState } from "@/components/mission-control/shared/EmptyState"

export function PortfolioRisks() {
  const { data } = useWorkspacePortfolio()

  const failed = data?.failedMissions ?? 0
  const total = (data?.activeMissions ?? 0) + (data?.completedMissions ?? 0) + failed

  if (failed === 0 && total === 0) {
    return (
      <section>
        <SectionHeader title="Portfolio Risks" />
        <div className="rounded-[12px] border border-[#EAEFF5] bg-white p-5">
          <EmptyState
            variant="shell"
            icon={
              <svg className="h-5 w-5 text-[#D1D5DB]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
              </svg>
            }
            title="No portfolio-level risks identified"
            description="Risks will aggregate from active missions and cross-initiative analysis"
          />
        </div>
      </section>
    )
  }

  return (
    <section>
      <SectionHeader title="Portfolio Risks" />

      <div className="rounded-[12px] border border-[#EAEFF5] bg-white p-5">
        <div className="space-y-3">
          {failed > 0 && (
            <div className="flex items-center justify-between rounded-[8px] border border-[#FEF2F2] bg-[#FEF2F2] px-4 py-3">
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-[#EF4444]" />
                <span className="text-[0.8rem] font-medium text-[#111827]">Failed Missions</span>
              </div>
              <span className="text-[0.9rem] font-bold text-[#EF4444]">{failed}</span>
            </div>
          )}
          <div className="flex items-center justify-between rounded-[8px] border border-[#E8EDF3] px-4 py-3">
            <span className="text-[0.8rem] text-[#6B7280]">Success rate</span>
            <span className="text-[0.8rem] font-semibold" style={{ color: (data?.successRate ?? 100) >= 90 ? "#38B88A" : "#F59E0B" }}>
              {data?.successRate ?? 100}%
            </span>
          </div>
          <div className="flex items-center justify-between rounded-[8px] border border-[#E8EDF3] px-4 py-3">
            <span className="text-[0.8rem] text-[#6B7280]">Queue depth</span>
            <span className="text-[0.8rem] font-semibold text-[#111827]">{data?.queueDepth ?? 0}</span>
          </div>
        </div>
      </div>
    </section>
  )
}
