"use client"

import { useWorkspaceIntelligence } from "@/hooks"
import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"

const CAPABILITIES = [
  { name: "Mission Planning", icon: "◆", color: "#38B88A", bg: "#ECFBF4" },
  { name: "Research", icon: "◇", color: "#3B82F6", bg: "#EFF6FF" },
  { name: "Browser Agent", icon: "◈", color: "#8B5CF6", bg: "#F5F3FF" },
  { name: "Computer Agent", icon: "⚙", color: "#F59E0B", bg: "#FFFBEB" },
]

export function CapabilityPanel() {
  const { data } = useWorkspaceIntelligence()

  const hasActivity = (data?.activeCount ?? 0) > 0

  return (
    <section>
      <SectionHeader title="Recommended Capabilities" />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {CAPABILITIES.map((cap) => (
          <div
            key={cap.name}
            className="rounded-[10px] border border-[#EAEFF5] bg-white p-4"
          >
            <p className="mb-2 text-[0.82rem] font-semibold text-[#111827]">{cap.name}</p>
            <p className="text-[0.7rem] text-[#6B7280]">
              {hasActivity ? `${data?.totalCount ?? 0} missions processed` : "Ready for use"}
            </p>
            <div className="mt-3 flex items-center gap-2">
              <div className="h-5 w-5 rounded-full" style={{ backgroundColor: cap.bg }}>
                <div className="h-full w-full flex items-center justify-center text-[0.55rem] font-bold" style={{ color: cap.color }}>
                  {data?.activeCount ?? 0}
                </div>
              </div>
              <span className="text-[0.65rem] text-[#9CA3AF]">{hasActivity ? "Available" : "Idle"}</span>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
