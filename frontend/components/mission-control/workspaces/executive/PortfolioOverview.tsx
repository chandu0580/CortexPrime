"use client"

import { useWorkspaceExecutive } from "@/hooks"
import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"
import { InfoCard } from "@/components/mission-control/shared/InfoCard"

export function PortfolioOverview() {
  const { data, isLoading } = useWorkspaceExecutive()

  const items = [
    { label: "Active Missions", value: isLoading ? "—" : String(data?.activeMissions ?? 0) },
    { label: "Active Agents", value: isLoading ? "—" : String(data?.activeAgents ?? 0) },
    { label: "Completed", value: isLoading ? "—" : String(data?.completedMissions ?? 0) },
    { label: "Failed", value: isLoading ? "—" : String(data?.failedMissions ?? 0) },
  ]

  return (
    <section>
      <SectionHeader title="Mission Portfolio Overview" />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {items.map((item) => (
          <InfoCard key={item.label}>
            <p className="mb-2 text-[0.78rem] font-medium text-[#111827]">{item.label}</p>
            <p className="text-[1.1rem] font-bold text-[#111827]">{item.value}</p>
          </InfoCard>
        ))}
      </div>
    </section>
  )
}
