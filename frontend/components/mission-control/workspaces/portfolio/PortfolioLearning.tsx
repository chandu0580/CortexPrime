"use client"

import { useWorkspacePortfolio } from "@/hooks"
import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"

export function PortfolioLearning() {
  const { data } = useWorkspacePortfolio()

  const totalCompleted = data?.completedMissions ?? 0
  const successRate = data?.successRate ?? 100

  const sections = [
    {
      label: "Lessons",
      count: totalCompleted > 0 ? totalCompleted : 0,
      active: totalCompleted > 0,
      summary: totalCompleted > 0 ? `${totalCompleted} missions completed` : "No entries",
    },
    {
      label: "Patterns",
      count: successRate >= 90 ? 1 : 0,
      active: successRate >= 90,
      summary: successRate >= 90 ? "High success rate" : "No entries",
    },
    {
      label: "Recommendations",
      count: data?.failedMissions ?? 0,
      active: (data?.failedMissions ?? 0) > 0,
      summary: (data?.failedMissions ?? 0) > 0 ? `${data?.failedMissions} failures to review` : "No entries",
    },
    {
      label: "Templates",
      count: 1,
      active: true,
      summary: "Standard mission template",
    },
  ]

  return (
    <section>
      <SectionHeader title="Portfolio Learning" />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {sections.map((section) => (
          <div
            key={section.label}
            className="rounded-[10px] bg-white p-4"
            style={{ border: `1px solid ${section.active ? "#D1D9E6" : "#D1D9E6"}`, borderStyle: section.active ? "solid" : "dashed" }}
          >
            <div
              className="mb-2 flex h-7 w-7 items-center justify-center rounded-[6px]"
              style={{ backgroundColor: section.active ? "#ECFBF4" : "#F8FAFC" }}
            >
              <div className="h-3 w-3 rounded" style={{ border: `1px solid ${section.active ? "#38B88A" : "#D1D5DB"}` }} />
            </div>
            <p className="text-[0.8rem] font-medium text-[#111827]">{section.label}</p>
            <p className="mt-1 text-[0.68rem]" style={{ color: section.active ? "#38B88A" : "#B0B7C3" }}>
              {section.summary}
            </p>
          </div>
        ))}
      </div>
    </section>
  )
}
