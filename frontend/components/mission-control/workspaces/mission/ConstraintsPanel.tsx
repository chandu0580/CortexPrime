"use client"

import { useWorkspaceMission } from "@/hooks"
import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"

export function ConstraintsPanel() {
  const { data } = useWorkspaceMission()
  const activeCount = data?.activeMissions.length ?? 0
  const failedCount = data?.failedCount ?? 0

  const constraintGroups = [
    {
      label: "Mission Load",
      items: [
        { text: `${activeCount} active missions`, met: activeCount > 0 },
        { text: `${data?.completedCount ?? 0} completed`, met: (data?.completedCount ?? 0) > 0 },
        { text: `${failedCount} failed`, met: failedCount > 0 },
      ],
    },
    {
      label: "System Capacity",
      items: [
        { text: "Missions queued", met: activeCount > 0 },
        { text: "Agents available", met: activeCount > 0 },
        { text: "Runtime active", met: true },
      ],
    },
    {
      label: "Completion Criteria",
      items: [
        { text: "Objective defined", met: activeCount > 0 },
        { text: "Execution started", met: activeCount > 0 },
        { text: "Results recorded", met: (data?.completedCount ?? 0) > 0 },
      ],
    },
    {
      label: "Operational Constraints",
      items: [
        { text: "System online", met: true },
        { text: "Resources available", met: activeCount < 10 },
        { text: "Queue depth nominal", met: activeCount < 5 },
      ],
    },
  ]

  return (
    <section>
      <SectionHeader title="Constraints" />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {constraintGroups.map((group) => (
          <div key={group.label} className="rounded-[10px] border border-[#EAEFF5] bg-white p-4">
            <p className="mb-2.5 text-[0.72rem] font-semibold uppercase tracking-wider text-[#9CA3AF]">
              {group.label}
            </p>
            <div className="space-y-2">
              {group.items.map((item, i) => (
                <div key={i} className="flex items-center gap-2">
                  <div
                    className="h-3 w-3 shrink-0 rounded-[3px]"
                    style={{
                      backgroundColor: item.met ? "#38B88A" : "#F0F4F8",
                      border: item.met ? "none" : "1px solid #D1D9E6",
                    }}
                  />
                  <span
                    className="text-[0.78rem]"
                    style={{ color: item.met ? "#374151" : "#9CA3AF" }}
                  >
                    {item.text}
                  </span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
