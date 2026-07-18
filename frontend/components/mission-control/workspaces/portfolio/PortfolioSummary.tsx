"use client"

import { useWorkspacePortfolio } from "@/hooks"
import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"
import { InfoCard } from "@/components/mission-control/shared/InfoCard"

export function PortfolioSummary() {
  const { data, isLoading } = useWorkspacePortfolio()

  const cards = [
    { label: "Business Goals", value: isLoading ? "—" : `${data?.activeMissions ?? 0} active` },
    { label: "Active Initiatives", value: isLoading ? "—" : String(data?.activeMissions ?? 0) },
    { label: "Mission Count", value: isLoading ? "—" : String((data?.activeMissions ?? 0) + (data?.completedMissions ?? 0) + (data?.failedMissions ?? 0)) },
    { label: "Portfolio Health", value: isLoading ? "—" : `${data?.successRate ?? 100}%` },
    { label: "Enterprise Alignment", value: isLoading ? "—" : data?.successRate != null && data.successRate >= 90 ? "Strong" : "Needs attention" },
  ]

  return (
    <section>
      <SectionHeader title="Portfolio Summary" suffix={<span className="text-[0.7rem] text-[#B0B7C3]">{data?.activeMissions ?? 0} active missions</span>} />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {cards.map((card) => (
          <InfoCard key={card.label} label={card.label}>{card.value}</InfoCard>
        ))}
      </div>
    </section>
  )
}
