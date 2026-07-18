"use client"

import { useActiveMissions, useRuntimeTelemetry } from "@/hooks"
import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"

export function StakeholdersPanel() {
  const { data: activeMissions } = useActiveMissions()
  const { data: telemetry } = useRuntimeTelemetry()

  const current = activeMissions?.[0]
  const agents = current?.assignedAgent
    ? [current.assignedAgent]
    : []
  const activeAgents = Number(telemetry?.active_agents ?? 0)

  const roles = [
    { label: "Business Owner", icon: "👤", assignee: "System" },
    { label: "Approver", icon: "✓", assignee: "Executive" },
    { label: "Operator", icon: "⚙", assignee: agents.length > 0 ? agents.join(", ") : "Runtime" },
    { label: "Observer", icon: "👁", assignee: current ? "Monitoring" : "—" },
    { label: "AI Coordinator", icon: "◆", assignee: current ? "Orchestrator" : "—" },
  ]

  return (
    <section>
      <SectionHeader title="Stakeholders" suffix={
        <span className="text-[0.7rem] text-[#B0B7C3]">{activeAgents} agents online</span>
      } />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {roles.map((role) => (
          <div
            key={role.label}
            className="rounded-[10px] border border-[#EAEFF5] bg-white p-4 text-center"
          >
            <div aria-hidden="true" className="mx-auto mb-2 flex h-9 w-9 items-center justify-center rounded-full bg-[#F0F4F8] text-[0.8rem] text-[#9CA3AF]">
              {role.icon}
            </div>
            <p className="text-[0.8rem] font-medium text-[#111827]">{role.label}</p>
            <p className="mt-1 text-[0.68rem]" style={{ color: role.assignee !== "—" ? "#38B88A" : "#B0B7C3" }}>
              {role.assignee !== "—" ? role.assignee : "Not assigned"}
            </p>
          </div>
        ))}
      </div>
    </section>
  )
}
