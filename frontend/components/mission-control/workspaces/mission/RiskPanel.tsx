"use client"

import { useWorkspaceMission } from "@/hooks"
import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"

export function RiskPanel() {
  const { data } = useWorkspaceMission()

  const failedCount = data?.failedCount ?? 0
  const activeCount = data?.activeMissions.length ?? 0
  const completedCount = data?.completedCount ?? 0
  const total = activeCount + completedCount + failedCount

  const risks = [
    {
      risk: "Mission failures",
      impact: failedCount > 0 ? "High" : "Low",
      likelihood: failedCount > 2 ? "High" : failedCount > 0 ? "Medium" : "Low",
      mitigation: failedCount > 0 ? "Review error logs" : "No failures detected",
    },
    {
      risk: "Queue overflow",
      impact: "Medium",
      likelihood: activeCount > 5 ? "High" : "Medium",
      mitigation: activeCount > 5 ? "Scale up agents" : "Within capacity",
    },
    {
      risk: "Completion rate",
      impact: "Medium",
      likelihood: total > 0 && completedCount / total < 0.5 ? "High" : "Low",
      mitigation: total > 0 && completedCount / total < 0.5 ? "Optimize execution pipeline" : "On track",
    },
  ]

  const riskColumns = ["Risk", "Impact", "Likelihood", "Mitigation"]

  return (
    <section>
      <SectionHeader title="Risk Assessment" />

      <div className="overflow-hidden rounded-[12px] border border-[#EAEFF5] bg-white">
        <div className="grid grid-cols-4 border-b border-[#EAEFF5] bg-[#F8FAFC]">
          {riskColumns.map((col) => (
            <div key={col} className="px-4 py-2.5 text-[0.7rem] font-semibold uppercase tracking-wider text-[#9CA3AF]">
              {col}
            </div>
          ))}
        </div>

        {risks.map((row, i) => (
          <div key={i} className="grid grid-cols-4 border-b border-[#EAEFF5] last:border-b-0">
            <div className="px-4 py-3">
              <span className="text-[0.78rem] font-medium text-[#374151]">{row.risk}</span>
            </div>
            <div className="px-4 py-3">
              <span className="text-[0.78rem]" style={{ color: row.impact === "High" ? "#EF4444" : row.impact === "Medium" ? "#F59E0B" : "#38B88A" }}>
                {row.impact}
              </span>
            </div>
            <div className="px-4 py-3">
              <span className="text-[0.78rem]" style={{ color: row.likelihood === "High" ? "#EF4444" : row.likelihood === "Medium" ? "#F59E0B" : "#38B88A" }}>
                {row.likelihood}
              </span>
            </div>
            <div className="px-4 py-3">
              <span className="text-[0.78rem] text-[#6B7280]">{row.mitigation}</span>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
