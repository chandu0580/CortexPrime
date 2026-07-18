"use client"

import { useWorkspaceIntelligence } from "@/hooks"
import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"

export function KnowledgePanel() {
  const { data } = useWorkspaceIntelligence()

  const recentMissions = data?.recentMissions ?? []
  const activeCount = data?.activeCount ?? 0
  const totalCount = data?.totalCount ?? 0

  const sections = [
    {
      label: "Related Missions",
      count: recentMissions.length,
      items: recentMissions.slice(0, 3).map((m) => m.goal),
      active: recentMissions.length > 0,
    },
    {
      label: "Knowledge Assets",
      count: totalCount,
      items: totalCount > 0 ? [`${activeCount} active`, `${totalCount - activeCount} archived`] : [],
      active: totalCount > 0,
    },
    {
      label: "Evidence",
      count: data?.successRate ?? 0,
      items: data?.successRate != null ? [`${data.successRate}% success rate`] : [],
      active: (data?.successRate ?? 0) > 0,
    },
    {
      label: "Templates",
      count: 1,
      items: ["Standard mission template"],
      active: true,
    },
  ]

  return (
    <section>
      <SectionHeader title="Knowledge Context" />

      <div className="rounded-[12px] border border-[#EAEFF5] bg-white p-5">
        <div className="grid grid-cols-4 gap-4">
          {sections.map((section) => (
            <div key={section.label} className="space-y-2">
              <div className="flex items-center gap-1.5">
                <div
                  className="h-3 w-3 rounded-[4px]"
                  style={{ backgroundColor: section.active ? "#ECFBF4" : "#F0F4F8" }}
                />
                <span className="text-[0.72rem] font-medium" style={{ color: section.active ? "#111827" : "#9CA3AF" }}>
                  {section.label}
                </span>
                {section.count > 0 && (
                  <span className="text-[0.65rem] font-bold text-[#38B88A]">({section.count})</span>
                )}
              </div>
              <div className="space-y-1">
                {section.items.length > 0 ? (
                  section.items.map((item, i) => (
                    <p key={i} className="text-[0.68rem] text-[#6B7280] truncate">{item}</p>
                  ))
                ) : (
                  <>
                    <div className="h-2.5 w-full rounded bg-[#F0F4F8]" />
                    <div className="h-2.5 w-4/5 rounded bg-[#F0F4F8]" />
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
        {recentMissions.length === 0 && (
          <p className="mt-4 text-center text-[0.72rem] text-[#B0B7C3]">
            Knowledge context will populate from related missions and organizational memory
          </p>
        )}
      </div>
    </section>
  )
}
