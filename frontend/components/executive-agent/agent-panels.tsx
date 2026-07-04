"use client"

import { useEffect } from "react"
import { useExecutiveAgentStore } from "@/store/executiveAgentStore"
import { GlassCard, StatusBadge, PulseDot } from "@/components/executive-platform/shared"
import { Bell, X, AlertTriangle, CheckCircle2, PlugZap, Shield, DollarSign, Lightbulb, TrendingUp } from "lucide-react"

export function NotificationCenter() {
  const { notifications, markRead, dismissNotification, startAgent } = useExecutiveAgentStore()

  useEffect(() => { startAgent() }, [startAgent])

  const severityColor = (s: string) => {
    if (s === "critical") return "text-red-400 bg-red-500/10 border-red-500/20"
    if (s === "warning") return "text-amber-400 bg-amber-500/10 border-amber-500/20"
    return "text-blue-400 bg-blue-500/10 border-blue-500/20"
  }

  const typeIcon = (t: string) => {
    if (t === "approval_required") return Shield
    if (t === "infrastructure_degraded" || t === "connector_failure") return PlugZap
    if (t === "security_alert") return AlertTriangle
    if (t === "cost_anomaly") return DollarSign
    if (t === "mission_completed") return CheckCircle2
    if (t === "mission_blocked") return AlertTriangle
    return Bell
  }

  return (
    <GlassCard>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Bell className="w-4 h-4 text-white/40" />
          <h2 className="text-sm font-medium text-white/60">Notifications</h2>
          {notifications.filter((n) => !n.read).length > 0 && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-red-500/20 text-red-400 font-medium">
              {notifications.filter((n) => !n.read).length}
            </span>
          )}
        </div>
        <PulseDot />
      </div>
      <div className="space-y-1 max-h-80 overflow-y-auto">
        {notifications.length === 0 ? (
          <div className="text-sm text-white/20 py-6 text-center">No notifications</div>
        ) : (
          notifications.map((n) => {
            const Icon = typeIcon(n.type)
            return (
              <div
                key={n.id}
                className={`flex items-start gap-2 p-2 rounded-lg text-sm transition-all hover:bg-white/[0.02] ${n.read ? "opacity-50" : ""}`}
                onClick={() => markRead(n.id)}
              >
                <Icon className={`w-3.5 h-3.5 mt-0.5 shrink-0 ${n.severity === "critical" ? "text-red-400" : n.severity === "warning" ? "text-amber-400" : "text-blue-400"}`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-white/80 text-xs font-medium">{n.title}</span>
                    <span className={`text-[9px] px-1 py-0.5 rounded ${severityColor(n.severity)}`}>{n.severity}</span>
                  </div>
                  <p className="text-[11px] text-white/40 mt-0.5">{n.description}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-[10px] text-white/20">{new Date(n.timestamp).toLocaleTimeString()}</span>
                    {n.action && <span className="text-[10px] text-emerald-400 hover:underline cursor-pointer">{n.action}</span>}
                  </div>
                </div>
                <button onClick={(e) => { e.stopPropagation(); dismissNotification(n.id) }} className="text-white/20 hover:text-white/60 shrink-0">
                  <X className="w-3 h-3" />
                </button>
              </div>
            )
          })
        )}
      </div>
    </GlassCard>
  )
}

export function SuggestionsPanel() {
  const { suggestions, dismissSuggestion } = useExecutiveAgentStore()

  const priorityColor = (p: string) => {
    if (p === "critical") return "border-red-500/20 bg-red-500/5"
    if (p === "high") return "border-amber-500/20 bg-amber-500/5"
    return "border-white/5 bg-white/[0.02]"
  }

  return (
    <GlassCard>
      <div className="flex items-center gap-2 mb-3">
        <Lightbulb className="w-4 h-4 text-amber-400" />
        <h2 className="text-sm font-medium text-white/60">Executive Suggestions</h2>
      </div>
      <div className="space-y-2">
        {suggestions.length === 0 ? (
          <div className="text-sm text-white/20 py-6 text-center">Analyzing platform state...</div>
        ) : (
          suggestions.map((s) => (
            <div key={s.id} className={`border rounded-lg p-3 transition-all ${priorityColor(s.priority)}`}>
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    {s.type === "security" && <Shield className="w-3.5 h-3.5 text-red-400" />}
                    {s.type === "cost" && <DollarSign className="w-3.5 h-3.5 text-violet-400" />}
                    {s.type === "infrastructure" && <PlugZap className="w-3.5 h-3.5 text-blue-400" />}
                    {(s.type === "mission" || s.type === "next_best_action") && <TrendingUp className="w-3.5 h-3.5 text-emerald-400" />}
                    <span className="text-sm text-white/80 font-medium">{s.action}</span>
                  </div>
                  <p className="text-xs text-white/40 mt-1">{s.description}</p>
                  <div className="flex items-center gap-2 mt-1.5">
                    <StatusBadge status={s.priority} />
                    <span className="text-[10px] text-white/20">{(s.confidence * 100).toFixed(0)}% confidence</span>
                  </div>
                </div>
                <button onClick={() => dismissSuggestion(s.id)} className="text-white/20 hover:text-white/60 shrink-0">
                  <X className="w-3 h-3" />
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </GlassCard>
  )
}