"use client"

import { useWorkspacePortfolio } from "@/hooks"
import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"
import { InfoCard } from "@/components/mission-control/shared/InfoCard"

export function OutcomeTracking() {
  const { data, isLoading } = useWorkspacePortfolio()

  const outcomes = [
    {
      label: "Expected Outcomes",
      icon: "▣",
      value: isLoading ? "—" : `${(data?.activeMissions ?? 0) + (data?.completedMissions ?? 0)} missions`,
    },
    {
      label: "Current Outcomes",
      icon: "◈",
      value: isLoading ? "—" : `${data?.completedMissions ?? 0} completed`,
    },
    {
      label: "Outcome Confidence",
      icon: "◇",
      value: isLoading ? "—" : `${data?.successRate ?? 100}%`,
    },
    {
      label: "Business Value",
      icon: "$",
      value: isLoading ? "—" : `${data?.completedMissions ?? 0} delivered`,
    },
  ]

  return (
    <section>
      <SectionHeader title="Outcome Tracking" />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {outcomes.map((item) => (
          <InfoCard key={item.label} icon={<span aria-hidden="true" className="text-[0.8rem] text-[#9CA3AF]">{item.icon}</span>} label={item.label}>
            <p className="mt-1 text-[0.84rem] font-semibold text-[#111827]">{item.value}</p>
          </InfoCard>
        ))}
      </div>
    </section>
  )
}
