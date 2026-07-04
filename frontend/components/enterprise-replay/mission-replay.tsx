"use client"

import { useEnterpriseReplayStore } from "@/store/enterpriseReplayStore"
import { Badge, Sparkline } from "./shared"
import {
  Target, Clock, Bot, BarChart3, Activity,
  CheckCircle2, TrendingUp, TriangleAlert, Workflow,
} from "lucide-react"

export function MissionReplayPanel() {
  const mission = useEnterpriseReplayStore((s) => s.mission)
  const isLoading = useEnterpriseReplayStore((s) => s.isLoading)

  if (isLoading) return <div className="text-center py-12 text-[0.82rem] text-[#6B7280]">Loading mission replay...</div>
  if (!mission?.found) return <div className="text-center py-12 text-[0.82rem] text-[#6B7280]">No mission replay data loaded</div>

  const metrics = [
    { label: "Total Events", value: String(mission.metrics?.total_events ?? 0), icon: Activity, tone: "completed" as const, data: [0] },
    { label: "Duration", value: mission.metrics?.duration_ms ? `${(mission.metrics.duration_ms as number / 1000).toFixed(1)}s` : "—", icon: Clock, tone: "info" as const },
    { label: "Agents", value: String((mission.metrics?.agents as string[])?.length ?? 0), icon: Bot, tone: "completed" as const },
    { label: "Avg Latency", value: mission.metrics?.avg_latency_ms ? `${(mission.metrics.avg_latency_ms as number).toFixed(0)}ms` : "—", icon: BarChart3, tone: "info" as const },
    { label: "Status", value: mission.status, icon: CheckCircle2, tone: mission.status === "completed" ? "completed" as const : "running" as const },
  ]

  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {metrics.map((m) => (
          <div key={m.label} className="rounded-[18px] border border-[#E8EDF3] bg-white p-4">
            <div className="flex items-start justify-between">
              <p className="text-[0.71rem] font-semibold text-[#9CA3AF]">{m.label}</p>
              <m.icon className="h-4 w-4 text-[#38B88A]" />
            </div>
            <p className="mt-1 text-[1.2rem] font-bold text-[#111827]">{m.value}</p>
          </div>
        ))}
      </div>

      <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-5">
        <h3 className="text-[0.95rem] font-bold text-[#111827] mb-4">Mission Stages</h3>
        <div className="flex items-center gap-1">
          {(mission.stages ?? []).map((stage, i) => (
            <div key={stage} className="flex items-center gap-1 flex-1">
              <div className={cn(
                "flex-1 h-2 rounded-full",
                i < ((mission.stages ?? []).length - 1) || mission.status === "completed"
                  ? "bg-[#38B88A]" : "bg-[#E8EDF3]"
              )} />
              <span className="text-[0.6rem] text-[#6B7280] font-medium whitespace-nowrap">{stage}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Cost */}
      {mission.cost && (
        <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-5">
          <h3 className="text-[0.95rem] font-bold text-[#111827] mb-2">Mission Cost</h3>
          <p className="text-[1.2rem] font-bold text-[#111827]">${String((mission.cost as Record<string, unknown>)?.total_cost ?? "0.00")}</p>
        </div>
      )}
    </div>
  )
}

function cn(...classes: (string | undefined | null | false)[]) {
  return classes.filter(Boolean).join(" ")
}
