"use client"

import { useWorkspaceExecutive } from "@/hooks"
import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"
import { InfoCard } from "@/components/mission-control/shared/InfoCard"

function formatTime(iso: string): string {
  try {
    const d = new Date(iso)
    if (!Number.isFinite(d.getTime())) return "--"
    return d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" })
  } catch {
    return "--"
  }
}

export function SituationSummary() {
  const { data, isLoading } = useWorkspaceExecutive()

  const cards = [
    {
      label: "Strategic Health",
      value: isLoading ? "—" : data?.systemStatus === "online" ? "Online" : data?.systemStatus === "degraded" ? "Degraded" : "Offline",
      color: data?.systemStatus === "online" ? "#38B88A" : data?.systemStatus === "degraded" ? "#F59E0B" : "#EF4444",
    },
    {
      label: "Active Missions",
      value: isLoading ? "—" : String(data?.activeMissions ?? 0),
    },
    {
      label: "Pending Decisions",
      value: isLoading ? "—" : String(data?.queueDepth ?? 0),
    },
    {
      label: "Critical Risks",
      value: isLoading ? "—" : data?.healthMatrix?.some((h) => h.status === "degraded" || h.score < 60) ? "⚠" : "None",
      color: data?.healthMatrix?.some((h) => h.status === "degraded" || h.score < 60) ? "#EF4444" : "#38B88A",
    },
    {
      label: "Enterprise Confidence",
      value: isLoading ? "—" : data?.autonomyScore != null ? `${data.autonomyScore}%` : "—",
    },
  ]

  return (
    <section>
      <SectionHeader
        title="Situation Summary"
        suffix={<span className="text-[0.7rem] text-[#B0B7C3]">Updated {data?.timestamp ? formatTime(data.timestamp) : "—"}</span>}
      />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {cards.map((card) => (
          <InfoCard key={card.label}>
            <p className="mb-2 text-[0.78rem] font-medium text-[#111827]">{card.label}</p>
            <p className="text-[1rem] font-bold" style={{ color: card.color ?? "#111827" }}>{card.value}</p>
          </InfoCard>
        ))}
      </div>
    </section>
  )
}
