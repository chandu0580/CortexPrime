"use client"

import { useEnterpriseData } from "@/services/enterprise/EnterpriseDataProvider"
import { GlassCard, PulseDot } from "@/components/executive-platform/shared"
import { Brain, RefreshCw, TrendingUp, AlertTriangle, DollarSign, Shield } from "lucide-react"

export default function LiveIntelligenceHub() {
  const data = useEnterpriseData()
  const snapshot = data.executiveSnapshot as Record<string, unknown> | null
  const analytics = data.executiveAnalytics as Record<string, unknown> | null
  const approvals = data.approvalSummary as Record<string, unknown> | null

  const recommendations: string[] = (snapshot?.recommendations as string[]) || []
  const series: Record<string, unknown>[] = (analytics?.series as Record<string, unknown>[]) || []
  const totals: Record<string, unknown> = (analytics?.totals as Record<string, unknown>) || {}

  if (data.isLoading && !snapshot) {
    return (
      <div className="max-w-7xl mx-auto space-y-6">
        <div className="h-8 w-48 bg-white/5 rounded animate-pulse" />
        <div className="grid grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-32 bg-white/5 rounded-xl animate-pulse" />)}
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Brain className="w-6 h-6 text-emerald-400" />
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Executive Intelligence</h1>
            <p className="text-xs text-white/40 mt-0.5 flex items-center gap-2">
              Live enterprise intelligence
              <PulseDot />
            </p>
          </div>
        </div>
        <button onClick={data.refreshAll} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-white/10 text-xs text-white/40 hover:text-white/60">
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <GlassCard>
          <div className="text-xs text-white/40 mb-1">Platform Health</div>
          <div className="text-lg font-semibold text-white/80 capitalize">{String(snapshot?.systemStatus || snapshot?.status || "unknown")}</div>
          <div className="text-[10px] text-white/20 mt-0.5">Active missions: {snapshot?.activeMissions as number ?? "—"}</div>
        </GlassCard>
        <GlassCard>
          <div className="text-xs text-white/40 mb-1">Pending Approvals</div>
          <div className={`text-lg font-semibold ${(approvals?.active as number) > 0 ? "text-amber-400" : "text-white/80"}`}>
            {approvals?.active as number ?? approvals?.pending_approvals as number ?? 0}
          </div>
          <div className="text-[10px] text-white/20 mt-0.5">Escalations: {approvals?.active_escalations as number ?? 0}</div>
        </GlassCard>
        <GlassCard>
          <div className="text-xs text-white/40 mb-1">System Status</div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-sm text-white/70">Operational</span>
          </div>
          {data.lastRefresh && <div className="text-[10px] text-white/20 mt-0.5">Updated {new Date(data.lastRefresh).toLocaleTimeString()}</div>}
        </GlassCard>
      </div>

      {recommendations.length > 0 && (
        <GlassCard>
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="w-4 h-4 text-emerald-400" />
            <h2 className="text-sm font-medium text-white/60">Live Recommendations</h2>
          </div>
          <div className="space-y-1.5">
            {recommendations.map((rec, i) => (
              <div key={i} className="flex items-start gap-2 text-sm text-white/50">
                {rec.toLowerCase().includes("risk") || rec.toLowerCase().includes("security")
                  ? <AlertTriangle className="w-3.5 h-3.5 text-amber-400 mt-0.5 shrink-0" />
                  : rec.toLowerCase().includes("cost")
                  ? <DollarSign className="w-3.5 h-3.5 text-violet-400 mt-0.5 shrink-0" />
                  : <Shield className="w-3.5 h-3.5 text-emerald-400 mt-0.5 shrink-0" />
                }
                {rec}
              </div>
            ))}
          </div>
        </GlassCard>
      )}

      {series.length > 0 && (
        <GlassCard>
          <h2 className="text-sm font-medium text-white/60 mb-2">7-Day Analytics</h2>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            {Object.entries(totals || {}).filter(([k]) => typeof k === "string" && !k.includes("date")).slice(0, 6).map(([key, val]) => (
              <div key={key} className="p-2 rounded-lg border border-white/5">
                <div className="text-[10px] text-white/30 capitalize">{key.replace(/_/g, " ")}</div>
                <div className="text-sm font-semibold text-white/80">{String(val)}</div>
              </div>
            ))}
          </div>
        </GlassCard>
      )}
    </div>
  )
}