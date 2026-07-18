"use client"

import { useActiveMissions, useMissionEvents } from "@/hooks"
import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"

export function ArtifactsPanel() {
  const { data: activeMissions } = useActiveMissions()
  const { data: events } = useMissionEvents()

  const current = activeMissions?.[0]
  const eventCount = events?.length ?? 0

  const artifactTypes = [
    {
      label: "Events",
      icon: "📋",
      count: eventCount,
      active: eventCount > 0,
    },
    {
      label: "Active Missions",
      icon: "📁",
      count: activeMissions?.length ?? 0,
      active: (activeMissions?.length ?? 0) > 0,
    },
    {
      label: "Executions",
      icon: "⚡",
      count: current ? 1 : 0,
      active: !!current,
    },
    {
      label: "Reports",
      icon: "📊",
      count: 0,
      active: false,
    },
  ]

  return (
    <section>
      <SectionHeader title="Artifacts" />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {artifactTypes.map((type) => (
          <div
            key={type.label}
            className="rounded-[10px] border border-[#EAEFF5] bg-white p-4"
            style={{ borderStyle: type.active ? "solid" : "dashed", borderColor: type.active ? "#D1D9E6" : "#D1D9E6" }}
          >
            <div
              className="mb-2 flex h-8 w-8 items-center justify-center rounded-[8px]"
              style={{ backgroundColor: type.active ? "#ECFBF4" : "#F8FAFC" }}
            >
              <span className="text-[0.8rem]">{type.icon}</span>
            </div>
            <p className="text-[0.8rem] font-medium text-[#111827]">{type.label}</p>
            <p className="mt-0.5 text-[0.68rem]" style={{ color: type.active ? "#38B88A" : "#B0B7C3" }}>
              {type.active ? `${type.count} available` : "No artifacts"}
            </p>
          </div>
        ))}
      </div>
    </section>
  )
}
