"use client"

import { useQuery } from "@tanstack/react-query"
import { api } from "@/services/api"
import { ExecPanel, EmptyPanel } from "./ExecPanel"
import { Clock, ArrowRight, Zap } from "lucide-react"

export function MissionQueuePanel() {
  const { data, isLoading } = useQuery({
    queryKey: ["command-center", "runtime-telemetry"],
    queryFn: () => api.get<{
      active_executions: number
      queue_depth: number
      total_completed: number
      total_failed: number
      active_agents: number
    }>("/api/telemetry/runtime"),
    refetchInterval: 15000,
  })

  const queueDepth = data?.queue_depth ?? 0
  const activeExecs = data?.active_executions ?? 0
  const completed = data?.total_completed ?? 0
  const failed = data?.total_failed ?? 0

  return (
    <ExecPanel
      title="Mission Queue"
      subtitle={`${queueDepth} queued`}
      accent="blue"
      loading={isLoading}
    >
      <div className="flex flex-col gap-3">
        <div className="grid grid-cols-3 gap-2">
          <div className="flex flex-col items-center p-2 rounded-lg bg-white/5">
            <span className="text-lg font-bold text-blue-400">{queueDepth}</span>
            <span className="text-[9px] text-white/30 uppercase">Queued</span>
          </div>
          <div className="flex flex-col items-center p-2 rounded-lg bg-white/5">
            <span className="text-lg font-bold text-emerald-400">{activeExecs}</span>
            <span className="text-[9px] text-white/30 uppercase">Active</span>
          </div>
          <div className="flex flex-col items-center p-2 rounded-lg bg-white/5">
            <span className="text-lg font-bold text-amber-400">{failed}</span>
            <span className="text-[9px] text-white/30 uppercase">Failed</span>
          </div>
        </div>

        <div className="space-y-1">
          <div className="flex items-center justify-between text-[10px]">
            <span className="text-white/30">Completed today</span>
            <span className="text-white/60 font-medium">{completed}</span>
          </div>
          <div className="w-full h-1.5 bg-white/5 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-emerald-500 to-emerald-400 rounded-full transition-all duration-500"
              style={{ width: `${completed + failed > 0 ? (completed / (completed + failed)) * 100 : 0}%` }}
            />
          </div>
          <div className="flex items-center justify-between text-[10px]">
            <span className="text-white/30">Success rate</span>
            <span className="text-emerald-400 font-medium">
              {completed + failed > 0 ? Math.round((completed / (completed + failed)) * 100) : 100}%
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 pt-1">
          <Zap className="w-3 h-3 text-amber-400" />
          <span className="text-[10px] text-white/30">
            Processing ~{Math.max(1, Math.round(activeExecs / 2))} missions/min
          </span>
        </div>
      </div>
    </ExecPanel>
  )
}