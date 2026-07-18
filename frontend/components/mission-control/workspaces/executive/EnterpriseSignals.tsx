"use client"

import { useWorkspaceExecutive } from "@/hooks"
import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"

export function EnterpriseSignals() {
  const { data } = useWorkspaceExecutive()

  const healthMap = Object.fromEntries(
    (data?.healthMatrix ?? []).map((h) => [h.label.toLowerCase(), h]),
  )

  const signalDomains = [
    {
      label: "Operational",
      icon: "⚙",
      status: healthMap["database"]?.status === "healthy" ? "Active" : healthMap["database"]?.status ?? "No signal",
      active: healthMap["database"]?.status === "healthy",
    },
    {
      label: "AI",
      icon: "◆",
      status: data?.activeMissions != null && data.activeMissions > 0 ? `${data.activeMissions} active` : "Idle",
      active: (data?.activeMissions ?? 0) > 0,
    },
    {
      label: "Agents",
      icon: "◈",
      status: data?.activeAgents != null && data.activeAgents > 0 ? `${data.activeAgents} active` : "Idle",
      active: (data?.activeAgents ?? 0) > 0,
    },
    {
      label: "System",
      icon: "♢",
      status: data?.systemStatus === "online" ? "Online" : data?.systemStatus ?? "No signal",
      active: data?.systemStatus === "online",
    },
    {
      label: "Safety",
      icon: "⚖",
      status: data?.safetyScore != null ? `${data.safetyScore}%` : "No signal",
      active: (data?.safetyScore ?? 0) >= 80,
    },
    {
      label: "Missions",
      icon: "☆",
      status: data?.totalMissions != null ? `${data.totalMissions} total` : "No signal",
      active: (data?.totalMissions ?? 0) > 0,
    },
  ]

  return (
    <section>
      <SectionHeader title="Enterprise Signals" />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {signalDomains.map((domain) => (
          <div
            key={domain.label}
            className="rounded-[10px] border border-[#EAEFF5] bg-white p-4 text-center"
          >
            <div aria-hidden="true" className="mx-auto mb-1.5 flex h-8 w-8 items-center justify-center rounded-full bg-[#F0F4F8] text-[0.8rem] text-[#9CA3AF]">
              {domain.icon}
            </div>
            <p className="text-[0.78rem] font-medium text-[#111827]">{domain.label}</p>
            <div className="mx-auto mt-2 flex items-center gap-1">
              <div
                className="h-1.5 w-1.5 rounded-full"
                style={{ backgroundColor: domain.active ? "#38B88A" : "#D1D5DB" }}
              />
              <span className="text-[0.65rem]" style={{ color: domain.active ? "#38B88A" : "#B0B7C3" }}>
                {domain.status}
              </span>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
