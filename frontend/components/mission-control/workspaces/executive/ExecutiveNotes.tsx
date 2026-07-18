"use client"

import { useWorkspaceExecutive } from "@/hooks"
import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"

export function ExecutiveNotes() {
  const { data } = useWorkspaceExecutive()

  return (
    <section>
      <SectionHeader title="Executive Notes" />

      <div className="min-h-[140px] rounded-[12px] border border-[#EAEFF5] bg-white p-5">
        {data?.currentMission ? (
          <div className="space-y-2">
            <p className="text-[0.82rem] font-medium text-[#111827]">
              Current Mission: {data.currentMission.goal}
            </p>
            <p className="text-[0.74rem] text-[#6B7280]">
              Stage: {data.currentMission.stage} · Progress: {data.currentMission.progress}% · Health: {data.currentMission.health}
            </p>
            <p className="text-[0.74rem] text-[#6B7280]">
              System Status: {data.systemStatus} · {data.activeAgents} active agents
            </p>
          </div>
        ) : (
          <p className="text-[0.82rem] italic text-[#B0B7C3]">
            Reserved for executive observations, strategic annotations, and mission commentary.
          </p>
        )}
      </div>
    </section>
  )
}
