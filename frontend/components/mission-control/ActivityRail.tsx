"use client"

import { Activity } from "lucide-react"
import { useActiveMissions, useRuntimeTelemetry } from "@/hooks"

export function ActivityRail() {
  const { data: activeMissions } = useActiveMissions()
  const { data: telemetry } = useRuntimeTelemetry()

  const activeCount = activeMissions?.length ?? 0
  const activeAgents = Number(telemetry?.active_agents ?? 0)
  const queueDepth = Number(telemetry?.queue_depth ?? 0)

  if (activeCount === 0 && activeAgents === 0) {
    return (
      <div className="flex h-[60px] items-center gap-3 border-t border-[#EAEFF5] bg-white px-5">
        <Activity className="h-4 w-4 text-[#D1D5DB]" />
        <span className="text-[0.78rem] text-[#B0B7C3]">No activity</span>
      </div>
    )
  }

  const statusParts: string[] = []
  if (activeCount > 0) statusParts.push(`${activeCount} mission${activeCount > 1 ? "s" : ""}`)
  if (activeAgents > 0) statusParts.push(`${activeAgents} agent${activeAgents > 1 ? "s" : ""}`)
  if (queueDepth > 0) statusParts.push(`${queueDepth} queued`)

  return (
    <div className="flex h-[60px] items-center gap-3 border-t border-[#EAEFF5] bg-white px-5">
      <Activity className="h-4 w-4 text-[#38B88A] animate-pulse" />
      <span className="text-[0.78rem] text-[#374151]">{statusParts.join(" · ")}</span>
    </div>
  )
}
