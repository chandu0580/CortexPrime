"use client"

import { useWorkspaceExecutive } from "@/hooks"
import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"

export function AttentionBoard() {
  const { data } = useWorkspaceExecutive()

  const healthIssues = data?.healthMatrix?.filter((h) => h.status !== "healthy" && h.status !== "online") ?? []
  const activeMissions = data?.activeMissions ?? 0
  const failedCount = data?.failedMissions ?? 0
  const totalMissions = data?.totalMissions ?? 0

  const tiers = [
    { label: "Critical", color: "#EF4444", bg: "#FEF2F2", count: healthIssues.filter((h) => h.score < 30).length },
    { label: "High", color: "#F59E0B", bg: "#FFFBEB", count: healthIssues.filter((h) => h.score >= 30 && h.score < 60).length },
    { label: "Medium", color: "#3B82F6", bg: "#EFF6FF", count: failedCount },
    { label: "Informational", color: "#9CA3AF", bg: "#F9FAFB", count: totalMissions },
  ]

  return (
    <section>
      <SectionHeader title="Executive Attention Board" />

      <div className="space-y-2">
        {tiers.map((tier) => (
          <div
            key={tier.label}
            className="rounded-[10px] border border-[#EAEFF5] bg-white px-4 py-3"
          >
            <div className="flex items-center gap-2.5">
              <div aria-hidden="true" className="flex h-7 w-7 items-center justify-center rounded-[6px]" style={{ backgroundColor: tier.bg }}>
                <div className="h-2 w-2 rounded-full" style={{ backgroundColor: tier.color }} />
              </div>
              <span className="text-[0.84rem] font-medium text-[#111827]">{tier.label}</span>
              <div className="ml-auto flex items-center gap-2">
                <span className="text-[0.9rem] font-bold" style={{ color: tier.color }}>{tier.count}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
