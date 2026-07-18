"use client"

import { useWorkspacePortfolio } from "@/hooks"
import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"

export function StrategicInitiatives() {
  const { data } = useWorkspacePortfolio()

  const activeCount = data?.activeMissions ?? 0
  const successRate = data?.successRate ?? 100

  const initiatives = [
    {
      name: "Mission Execution",
      status: activeCount > 0 ? "Running" : "Idle",
      active: activeCount > 0,
      color: "#38B88A",
    },
    {
      name: "Quality Assurance",
      status: successRate >= 90 ? "Passing" : "Needs review",
      active: successRate >= 90,
      color: successRate >= 90 ? "#38B88A" : "#F59E0B",
    },
    {
      name: "Resource Optimization",
      status: `${data?.activeAgents ?? 0} agents`,
      active: (data?.activeAgents ?? 0) > 0,
      color: "#3B82F6",
    },
    {
      name: "Portfolio Growth",
      status: `${activeCount + (data?.completedMissions ?? 0)} total`,
      active: activeCount + (data?.completedMissions ?? 0) > 0,
      color: "#8B5CF6",
    },
  ]

  return (
    <section>
      <SectionHeader title="Strategic Initiatives" />

      <div className="rounded-[12px] border border-[#EAEFF5] bg-white p-5">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {initiatives.map((init) => (
            <div
              key={init.name}
              className="flex flex-col items-center justify-center rounded-[10px] py-6"
              style={{ border: `1px solid ${init.active ? `${init.color}30` : "#D1D9E6"}`, backgroundColor: init.active ? `${init.color}05` : "white", borderStyle: init.active ? "solid" : "dashed" }}
            >
              <div className="mb-2 flex h-8 w-8 items-center justify-center rounded-[8px]" style={{ backgroundColor: `${init.color}15` }}>
                <div className="h-4 w-4 rounded-full" style={{ backgroundColor: init.color }} />
              </div>
              <p className="text-[0.76rem] font-medium" style={{ color: init.active ? "#111827" : "#9CA3AF" }}>{init.name}</p>
              <p className="mt-0.5 text-[0.66rem]" style={{ color: init.active ? init.color : "#B0B7C3" }}>
                {init.status}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
