"use client"

import { useExecutiveAgentStore } from "@/store/executiveAgentStore"
import { GlassCard } from "@/components/executive-platform/shared"
import { History, Crosshair, CheckCircle2, Shield, Lightbulb, AlertTriangle } from "lucide-react"

export function ExecutiveTimeline() {
  const { timeline } = useExecutiveAgentStore()

  const now = new Date()
  const today = timeline.filter((e) => e.category === "today")
  const yesterday = timeline.filter((e) => e.category === "yesterday")
  const lastWeek = timeline.filter((e) => e.category === "last_week")

  const typeIcon = (t: string) => {
    if (t === "mission") return Crosshair
    if (t === "approval") return Shield
    if (t === "recommendation") return Lightbulb
    if (t === "alert") return AlertTriangle
    if (t === "decision") return CheckCircle2
    return History
  }

  const renderEntries = (entries: typeof timeline) => {
    if (entries.length === 0) return <div className="text-xs text-white/20 py-3 text-center">No entries</div>
    return entries.map((e) => {
      const Icon = typeIcon(e.type)
      return (
        <div key={e.id} className="flex items-start gap-2 py-1.5 text-xs">
          <Icon className="w-3 h-3 mt-0.5 shrink-0 text-white/30" />
          <div className="flex-1 min-w-0">
            <span className="text-white/60">{e.title}</span>
            <p className="text-white/30 truncate">{e.description}</p>
          </div>
          <span className="text-[10px] text-white/20 shrink-0">{new Date(e.timestamp).toLocaleTimeString()}</span>
        </div>
      )
    })
  }

  return (
    <GlassCard>
      <div className="flex items-center gap-2 mb-3">
        <History className="w-4 h-4 text-white/40" />
        <h2 className="text-sm font-medium text-white/60">Executive Timeline</h2>
      </div>

      <div className="space-y-3">
        <div>
          <h3 className="text-[10px] text-white/30 uppercase tracking-wider mb-1">Today</h3>
          <div className="border-l border-white/5 pl-3">{renderEntries(today)}</div>
        </div>
        <div>
          <h3 className="text-[10px] text-white/30 uppercase tracking-wider mb-1">Yesterday</h3>
          <div className="border-l border-white/5 pl-3">{renderEntries(yesterday)}</div>
        </div>
        <div>
          <h3 className="text-[10px] text-white/30 uppercase tracking-wider mb-1">Last Week</h3>
          <div className="border-l border-white/5 pl-3">{renderEntries(lastWeek)}</div>
        </div>
      </div>
    </GlassCard>
  )
}

export function MissionPreparationPanel() {
  const { missionPreparations } = useExecutiveAgentStore()

  return (
    <GlassCard>
      <div className="flex items-center gap-2 mb-3">
        <Crosshair className="w-4 h-4 text-blue-400" />
        <h2 className="text-sm font-medium text-white/60">Prepared Missions</h2>
      </div>
      <div className="space-y-2">
        {missionPreparations.map((mp) => (
          <div key={mp.id} className="border border-white/5 rounded-lg p-3">
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm text-white/80 font-medium">{mp.name}</span>
              <span className={`text-[10px] px-2 py-0.5 rounded-full border font-medium uppercase ${
                mp.riskLevel === "high" ? "text-orange-400 border-orange-500/20 bg-orange-500/10" :
                mp.riskLevel === "low" ? "text-emerald-400 border-emerald-500/20 bg-emerald-500/10" :
                "text-amber-400 border-amber-500/20 bg-amber-500/10"
              }`}>{mp.riskLevel}</span>
            </div>
            <p className="text-xs text-white/40 mb-1.5">{mp.description}</p>
            <div className="flex flex-wrap gap-1 text-[10px] text-white/30">
              {mp.requiredWorkers.map((w) => <span key={w} className="px-1.5 py-0.5 rounded bg-white/5">{w}</span>)}
              <span className="text-white/20">·</span>
              <span>{mp.estimatedDuration}</span>
              {mp.approvalRequired && <span className="text-amber-400/60">· Approval required</span>}
            </div>
          </div>
        ))}
      </div>
    </GlassCard>
  )
}