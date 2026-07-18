"use client"

import { useWorkspaceMission, useActiveMissions } from "@/hooks"
import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"

export function MissionOverview() {
  const { data: active } = useActiveMissions()
  const { data, isLoading } = useWorkspaceMission()

  const currentMission = active?.[0] ?? data?.activeMissions[0]

  if (!currentMission) {
    return (
      <section>
        <SectionHeader
          title="Mission Overview"
          suffix={
            <div className="flex h-6 items-center gap-1.5 rounded-[6px] bg-[#F0F4F8] px-2.5 text-[0.65rem] font-medium uppercase tracking-wider text-[#9CA3AF]">
              <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-[#D1D5DB]" />
              Draft
            </div>
          }
        />

        <div className="rounded-[12px] border border-[#EAEFF5] bg-white p-5">
          <p className="text-[0.84rem] text-[#9CA3AF] text-center py-4">No active mission selected</p>
        </div>
      </section>
    )
  }

  return (
    <section>
      <SectionHeader
        title="Mission Overview"
        suffix={
          <div className="flex h-6 items-center gap-1.5 rounded-[6px] bg-[#ECFBF4] px-2.5 text-[0.65rem] font-medium uppercase tracking-wider text-[#38B88A]">
            <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-[#38B88A]" />
            {currentMission.status}
          </div>
        }
      />

      <div className="rounded-[12px] border border-[#EAEFF5] bg-white p-5">
        <div className="grid grid-cols-1 gap-x-8 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <p className="text-[0.7rem] font-medium uppercase tracking-wider text-[#9CA3AF]">Mission Title</p>
            <p className="text-[0.84rem] font-semibold text-[#111827] mt-1">{currentMission.goal}</p>
          </div>
          <div>
            <p className="text-[0.7rem] font-medium uppercase tracking-wider text-[#9CA3AF]">Execution ID</p>
            <p className="text-[0.84rem] text-[#111827] mt-1 font-mono text-[0.75rem]">{currentMission.execution_id}</p>
          </div>
          <div>
            <p className="text-[0.7rem] font-medium uppercase tracking-wider text-[#9CA3AF]">Status</p>
            <p className="text-[0.84rem] font-semibold text-[#111827] mt-1" style={{ color: currentMission.status === "completed" ? "#38B88A" : currentMission.status === "failed" ? "#EF4444" : "#111827" }}>
              {currentMission.status}
            </p>
          </div>
          <div>
            <p className="text-[0.7rem] font-medium uppercase tracking-wider text-[#9CA3AF]">Agent</p>
            <p className="text-[0.84rem] text-[#111827] mt-1">{currentMission.assignedAgent ?? "Unassigned"}</p>
          </div>
          <div>
            <p className="text-[0.7rem] font-medium uppercase tracking-wider text-[#9CA3AF]">Started</p>
            <p className="text-[0.84rem] text-[#111827] mt-1">{currentMission.startedAt ? new Date(currentMission.startedAt).toLocaleString() : "—"}</p>
          </div>
          <div>
            <p className="text-[0.7rem] font-medium uppercase tracking-wider text-[#9CA3AF]">Missions in queue</p>
            <p className="text-[0.84rem] font-semibold text-[#111827] mt-1">{data?.activeMissions.length ?? 0} active</p>
          </div>
        </div>
      </div>
    </section>
  )
}
