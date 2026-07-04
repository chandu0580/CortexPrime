"use client"

import { useEnterpriseData } from "@/services/enterprise/EnterpriseDataProvider"
import { GlassCard, PulseDot, StatusBadge } from "@/components/executive-platform/shared"
import { Activity, AlertTriangle, CheckCircle2, Clock, Crosshair, MessageSquare, PlugZap, ShieldCheck, RefreshCw } from "lucide-react"

export default function LiveExecutiveHome() {
  const data = useEnterpriseData()

  const health = data.health as Record<string, unknown> | null
  const snapshot = data.executiveSnapshot as Record<string, unknown> | null
  const infra = data.runtimeInfrastructure as Record<string, unknown> | null
  const telemetry = data.runtimeTelemetry as Record<string, unknown> | null
  const approvals = data.approvalSummary as Record<string, unknown> | null
  const cost = data.costSummary as Record<string, unknown> | null

  const systemStatus: string = (snapshot?.systemStatus as string) || (snapshot?.status as string) || (health?.status as string) || "loading"
  const activeMissions: number = (telemetry?.active_executions as number) ?? (snapshot?.activeMissions as number) ?? 0
  const activeAgents: number = (telemetry?.active_agents as number) ?? (snapshot?.activeAgents as number) ?? 0
  const completedMissions: number = (telemetry?.total_completed as number) ?? 0
  const failedMissions: number = (telemetry?.total_failed as number) ?? 0
  const pendingApprovals: number = (approvals?.active as number) ?? (approvals?.pending_approvals as number) ?? 0

  const recommendations: string[] = (snapshot?.recommendations as string[]) || []
  const agents: Record<string, unknown>[] = (telemetry?.agents as Record<string, unknown>[]) || []
  const recentExecutions: Record<string, unknown>[] = (telemetry?.recent_executions as Record<string, unknown>[]) || []

  const kpis = [
    { label: "Active Missions", value: activeMissions, icon: Crosshair, color: "text-emerald-400" },
    { label: "Completed", value: completedMissions, icon: CheckCircle2, color: "text-blue-400" },
    { label: "Active Agents", value: activeAgents, icon: Activity, color: "text-violet-400" },
    { label: "Pending Approvals", value: pendingApprovals, icon: ShieldCheck, color: pendingApprovals > 0 ? "text-amber-400" : "text-white/40" },
    { label: "Failed Missions", value: failedMissions, icon: AlertTriangle, color: failedMissions > 0 ? "text-red-400" : "text-white/40" },
  ]

  if (data.isLoading && !data.health) {
    return (
      <div className="max-w-7xl mx-auto space-y-6">
        <div className="h-8 w-64 bg-white/5 rounded animate-pulse" />
        <div className="grid grid-cols-5 gap-3">
          {Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-24 bg-white/5 rounded-xl animate-pulse" />)}
        </div>
        <div className="h-64 bg-white/5 rounded-xl animate-pulse" />
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-tight">Executive Home</h1>
            <PulseDot />
          </div>
          <p className="text-sm text-white/40 mt-1">
            {new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })}
            {data.lastRefresh && <span className="text-white/20 ml-2">· Updated {new Date(data.lastRefresh).toLocaleTimeString()}</span>}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {data.errors.length > 0 && (
            <div className="text-[10px] text-amber-400/60">{data.errors.length} issue(s)</div>
          )}
          <button onClick={data.refreshAll} className="p-1.5 rounded-lg hover:bg-white/5 text-white/30 hover:text-white/60">
            <RefreshCw className="w-4 h-4" />
          </button>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full border border-emerald-500/20 bg-emerald-500/5">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-xs text-emerald-400 font-medium uppercase tracking-wider">{systemStatus}</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {kpis.map((kpi) => (
          <GlassCard key={kpi.label}>
            <div className="flex items-center gap-2 text-xs text-white/40 mb-2">
              <kpi.icon className={`w-3.5 h-3.5 ${kpi.color}`} />
              {kpi.label}
            </div>
            <div className={`text-2xl font-semibold ${kpi.color}`}>{kpi.value}</div>
          </GlassCard>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <GlassCard className="lg:col-span-2">
          <h2 className="text-sm font-medium text-white/60 mb-3">Infrastructure Health</h2>
          <div className="grid grid-cols-2 gap-2">
            {Object.entries({
              ...(infra as Record<string, unknown> || {}),
              ...(health?.infrastructure as Record<string, unknown> || {}),
            }).filter(([k]) => !["event_bus", "agent_registry", "websocket"].includes(k)).slice(0, 6).map(([name, status]) => (
              <div key={name} className="flex items-center gap-2 p-2.5 rounded-lg border border-white/5">
                {String(status).includes("connected") || String(status).includes("available") || String(status).includes("healthy")
                  ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                  : <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                }
                <div>
                  <div className="text-xs capitalize text-white/40">{name}</div>
                  <div className="text-xs text-white/60">{String(status)}</div>
                </div>
              </div>
            ))}
          </div>
          {agents.length > 0 && (
            <div className="mt-3 pt-3 border-t border-white/5">
              <h3 className="text-xs text-white/40 mb-1.5">Registered Agents ({agents.length})</h3>
              <div className="flex flex-wrap gap-1">
                {agents.slice(0, 10).map((a: Record<string, unknown>, i) => (
                  <StatusBadge key={i} status={String(a.status || "idle")} label={String(a.name || a.agent || `agent_${i}`)} />
                ))}
              </div>
            </div>
          )}
        </GlassCard>

        <GlassCard>
          <h2 className="text-sm font-medium text-white/60 mb-3">Quick Actions</h2>
          <div className="space-y-1">
            {[
              { icon: Crosshair, label: "New Mission", href: "/executive-platform/mission-control" },
              { icon: MessageSquare, label: "Executive Chat", href: "/executive-platform/chat" },
              { icon: PlugZap, label: "View Connectors", href: "/executive-platform/connectors" },
            ].map((action) => (
              <a key={action.label} href={action.href}
                className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-white/50 hover:text-white hover:bg-white/5 transition-all"
              ><action.icon className="w-4 h-4" />{action.label}</a>
            ))}
          </div>
          {recentExecutions.length > 0 && (
            <div className="mt-3 pt-3 border-t border-white/5">
              <h3 className="text-xs text-white/40 mb-1.5">Recent Executions</h3>
              <div className="space-y-1">
                {recentExecutions.slice(0, 3).map((e: Record<string, unknown>, i) => (
                  <div key={i} className="text-[10px] text-white/30 truncate">
                    {String(e.objective || e.execution_id || `exec_${i}`).slice(0, 40)}
                  </div>
                ))}
              </div>
            </div>
          )}
        </GlassCard>
      </div>

      {recommendations.length > 0 && (
        <GlassCard>
          <h2 className="text-sm font-medium text-white/60 mb-2">System Recommendations</h2>
          <ul className="space-y-1">
            {recommendations.map((rec, i) => (
              <li key={i} className="text-sm text-white/40 flex items-start gap-2">
                <span className="text-emerald-400 mt-0.5">•</span>
                {rec}
              </li>
            ))}
          </ul>
        </GlassCard>
      )}
    </div>
  )
}