"use client"

import { Crosshair, AlertTriangle, TrendingUp, Clock, Zap, BarChart3 } from "lucide-react"
import { GlassCard, StatusBadge, KpiCard } from "@/components/executive-platform/shared"
import type { MissionIntelligence } from "@/services/intelligence/executiveIntelligence"

export function MissionIntelligencePanel({ missions }: { missions: MissionIntelligence[] }) {
  if (missions.length === 0) {
    return (
      <GlassCard>
        <div className="flex items-center gap-2 mb-3">
          <Crosshair className="w-4 h-4 text-blue-400" />
          <h2 className="text-sm font-medium text-white/60">Mission Intelligence</h2>
        </div>
        <div className="text-sm text-white/30 py-6 text-center">No active missions to analyze</div>
      </GlassCard>
    )
  }

  return (
    <GlassCard>
      <div className="flex items-center gap-2 mb-3">
        <Crosshair className="w-4 h-4 text-blue-400" />
        <h2 className="text-sm font-medium text-white/60">Mission Intelligence</h2>
      </div>
      <div className="space-y-3">
        {missions.map((m) => (
          <div key={m.missionId} className="border border-white/5 rounded-lg p-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-white/80 font-medium">{m.name}</span>
              <StatusBadge status={m.probabilityOfSuccess > 0.7 ? "healthy" : m.probabilityOfSuccess > 0.4 ? "degraded" : "failed"} label={`${(m.probabilityOfSuccess * 100).toFixed(0)}%`} />
            </div>
            <div className="flex items-center gap-4 text-xs text-white/40 mb-2">
              <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{m.estimatedCompletion}</span>
              {m.currentBottleneck && <span className="flex items-center gap-1"><AlertTriangle className="w-3 h-3 text-amber-400" />{m.currentBottleneck}</span>}
            </div>
            {m.suggestedActions.length > 0 && (
              <div className="space-y-1 mt-2 pt-2 border-t border-white/5">
                <span className="text-[10px] text-white/30 uppercase tracking-wider">Suggested Actions</span>
                {m.suggestedActions.map((a, i) => (
                  <div key={i} className="flex items-center gap-1.5 text-xs text-emerald-400">
                    <Zap className="w-3 h-3 shrink-0" />
                    {a}
                  </div>
                ))}
              </div>
            )}
            {m.predictedBlockers.length > 0 && (
              <div className="mt-2 pt-2 border-t border-white/5">
                <span className="text-[10px] text-white/30 uppercase tracking-wider">Predicted Blockers</span>
                {m.predictedBlockers.map((b, i) => (
                  <div key={i} className="flex items-center gap-1.5 text-xs text-amber-400 mt-1">
                    <AlertTriangle className="w-3 h-3 shrink-0" />
                    {b}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </GlassCard>
  )
}

export function ConnectorIntelligencePanel({ connectors }: { connectors: { name: string; status: string; healthScore: number; latency: string; recentActivity: string; recommendedAction: string | null }[] }) {
  if (connectors.length === 0) return null
  return (
    <GlassCard>
      <div className="flex items-center gap-2 mb-3">
        <BarChart3 className="w-4 h-4 text-violet-400" />
        <h2 className="text-sm font-medium text-white/60">Connector Intelligence</h2>
      </div>
      <div className="space-y-2">
        {connectors.map((c) => (
          <div key={c.name} className="flex items-center gap-3 p-2 rounded-lg hover:bg-white/[0.02]">
            <div className={`w-2 h-2 rounded-full ${c.status === "healthy" ? "bg-emerald-400" : c.status === "degraded" ? "bg-amber-400" : "bg-red-400"}`} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between">
                <span className="text-sm text-white/70">{c.name}</span>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-white/30">{c.latency}</span>
                  <span className={`text-xs ${c.healthScore > 90 ? "text-emerald-400" : c.healthScore > 70 ? "text-amber-400" : "text-red-400"}`}>{c.healthScore}%</span>
                </div>
              </div>
              <div className="flex items-center justify-between mt-0.5">
                <span className="text-[10px] text-white/20">{c.recentActivity}</span>
                {c.recommendedAction && <span className="text-[10px] text-emerald-400">{c.recommendedAction}</span>}
              </div>
            </div>
          </div>
        ))}
      </div>
    </GlassCard>
  )
}

export function LiveIntelligenceFeed() {
  const events = [
    { time: "now", type: "mission", text: "Mission updated: Knowledge Discovery — progressing" },
    { time: "2s ago", type: "system", text: "WebSocket reconnected after brief interruption" },
    { time: "5s ago", type: "approval", text: "Approval request wf_001 escalated to Executive" },
    { time: "12s ago", type: "connector", text: "GitHub webhook received: push to main" },
    { time: "25s ago", type: "memory", text: "Semantic memory updated: project configuration" },
  ]

  return (
    <GlassCard>
      <div className="flex items-center gap-2 mb-3">
        <Zap className="w-4 h-4 text-emerald-400" />
        <h2 className="text-sm font-medium text-white/60">Live Intelligence Feed</h2>
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse ml-auto" />
      </div>
      <div className="space-y-0.5 max-h-64 overflow-y-auto">
        {events.map((ev, i) => (
          <div key={i} className="flex items-start gap-2 px-2 py-1.5 rounded hover:bg-white/[0.02] text-xs">
            <span className="text-white/20 w-14 shrink-0">{ev.time}</span>
            <div className={`w-1.5 h-1.5 rounded-full mt-1 shrink-0 ${ev.type === "mission" ? "bg-blue-400" : ev.type === "approval" ? "bg-amber-400" : ev.type === "connector" ? "bg-violet-400" : ev.type === "memory" ? "bg-emerald-400" : "bg-white/30"}`} />
            <span className="text-white/50">{ev.text}</span>
          </div>
        ))}
      </div>
    </GlassCard>
  )
}