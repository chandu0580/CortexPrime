"use client"

import { useState, useMemo } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Clock, FileText, BarChart3, Activity, Server, Shield,
  RefreshCw, Play, Layers, AlertTriangle, CheckCircle,
  ArrowRight, Globe, Database, BookOpen, Terminal,
  Target, Wifi, XCircle, DollarSign, Zap,
} from "lucide-react"
import { useMissionStore, MISSION_STAGES } from "@/store/missionStore"
import { cn } from "@/utils/cn"
import { dur, ease } from "@/lib/motion-tokens"
import { useActiveMissions, useMissionEvents, useRuntimeTelemetry, useMissionReplayTimeline, useMissionWebSocket } from "@/hooks"
import { useDashboardHealth } from "@/hooks"
import type { MissionSummaryItem } from "@/services/mission-control/missions"

type DetailTab =
  | "timeline" | "planner" | "connectors" | "verification"
  | "resources" | "logs" | "metrics" | "replay" | "audit"

const DETAIL_TABS: { id: DetailTab; label: string; icon: React.ReactNode }[] = [
  { id: "timeline", label: "Timeline", icon: <Clock size={14} /> },
  { id: "planner", label: "Planner", icon: <FileText size={14} /> },
  { id: "connectors", label: "Connectors", icon: <Globe size={14} /> },
  { id: "verification", label: "Verification", icon: <Shield size={14} /> },
  { id: "resources", label: "Resources", icon: <Database size={14} /> },
  { id: "logs", label: "Logs", icon: <Terminal size={14} /> },
  { id: "metrics", label: "Metrics", icon: <BarChart3 size={14} /> },
  { id: "replay", label: "Replay", icon: <RefreshCw size={14} /> },
  { id: "audit", label: "Audit", icon: <BookOpen size={14} /> },
]

function StageBadge({ stage }: { stage: string }) {
  const colors: Record<string, string> = {
    initialized: "bg-blue-500",
    planning: "bg-purple-500",
    researching: "bg-cyan-500",
    executing: "bg-amber-500",
    validating: "bg-orange-500",
    reflecting: "bg-indigo-500",
    completed: "bg-green-500",
    running: "bg-blue-500",
    failed: "bg-red-500",
    queued: "bg-gray-400",
  }
  const color = colors[stage] || "bg-gray-400"
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold text-white", color)}>
      <span className="h-1.5 w-1.5 rounded-full bg-white/60" />
      {stage.charAt(0).toUpperCase() + stage.slice(1)}
    </span>
  )
}

function Section({ title, icon, children }: { title?: string; icon?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="rounded-[16px] border border-[#E8EDF3] bg-white p-5 shadow-sm">
      {title && (
        <div className="mb-4 flex items-center gap-2">
          {icon && <span className="text-gray-400">{icon}</span>}
          <h3 className="text-[0.9rem] font-bold text-[#111827]">{title}</h3>
        </div>
      )}
      {children}
    </div>
  )
}

function relativeTime(iso: string | null | undefined): string {
  if (!iso) return ""
  const d = new Date(iso)
  if (!Number.isFinite(d.getTime())) return ""
  const s = Math.floor((Date.now() - d.getTime()) / 1000)
  if (s < 60) return `${s}s ago`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  return d.toLocaleDateString()
}

function formatTime(iso: string | null | undefined): string {
  if (!iso) return "--"
  const d = new Date(iso)
  if (!Number.isFinite(d.getTime())) return "--"
  return d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" })
}

export function MissionDetailsPanel() {
  const [activeDetail, setActiveDetail] = useState<DetailTab>("timeline")

  useMissionWebSocket()

  const { data: activeMissions, isLoading: missionsLoading } = useActiveMissions()
  const { data: events, isLoading: eventsLoading } = useMissionEvents()
  const { data: telemetry } = useRuntimeTelemetry()
  const { data: health } = useDashboardHealth()

  const currentMission: MissionSummaryItem | undefined = activeMissions?.[0]
  const missionEvents = events ?? []
  const currentExecId = currentMission?.execution_id ?? null

  const { data: replayTimeline } = useMissionReplayTimeline(currentExecId)

  const missionLogs = useMemo(() => {
    return missionEvents
      .filter((ev) => ev && typeof ev === "object")
      .slice(0, 50)
      .map((ev) => ({
        time: formatTime((ev as Record<string, unknown>).timestamp as string),
        level: ((ev as Record<string, unknown>).status as string) ?? "info",
        msg: ((ev as Record<string, unknown>).message as string) ?? ((ev as Record<string, unknown>).event_type as string) ?? "",
        agent: (ev as Record<string, unknown>).agent as string,
      }))
      .filter((l) => l.msg)
  }, [missionEvents])

  const replayEvents = useMemo(() => {
    if (!replayTimeline || !Array.isArray(replayTimeline)) return []
    return replayTimeline.slice(0, 20)
  }, [replayTimeline])

  const successRate = useMemo(() => {
    if (!telemetry) return null
    const tc = Number((telemetry as Record<string, unknown>).total_completed ?? 0)
    const tf = Number((telemetry as Record<string, unknown>).total_failed ?? 0)
    const total = tc + tf
    return total > 0 ? Math.round((tc / total) * 100) : null
  }, [telemetry])

  const formatTimeShort = (iso: string | null | undefined) => {
    if (!iso) return "--"
    const d = new Date(iso)
    if (!Number.isFinite(d.getTime())) return "--"
    return d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit" })
  }

  return (
    <div className="flex flex-col gap-5">
      {/* Mission header */}
      <Section>
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              <Target size={16} className="text-[#38B88A]" />
              <h2 className="text-[1.1rem] font-extrabold text-[#111827] tracking-tight">
                {currentMission?.goal ?? "No active mission"}
              </h2>
              {currentMission && <StageBadge stage={currentMission.status} />}
            </div>
            <div className="flex items-center gap-4 text-[0.72rem] text-[#6B7280]">
              <span>Started: {formatTimeShort(currentMission?.startedAt)}</span>
              {currentMission?.completedAt && <span>Completed: {formatTimeShort(currentMission.completedAt)}</span>}
              {currentMission && (
                <span className="flex items-center gap-1">
                  <Activity size={12} />
                  {currentMission.assignedAgent ? `Agent: ${currentMission.assignedAgent}` : "No agent assigned"}
                </span>
              )}
            </div>
          </div>
        </div>
      </Section>

      {/* Tab navigation */}
      <div className="flex flex-wrap gap-1.5">
        {DETAIL_TABS.map((tab) => {
          const isActive = activeDetail === tab.id
          return (
            <button
              key={tab.id}
              onClick={() => setActiveDetail(tab.id)}
              className={cn(
                "flex items-center gap-1.5 rounded-[10px] px-3 py-2 text-[0.72rem] font-semibold transition-all",
                isActive
                  ? "bg-[#ECFBF4] text-[#2F9F77] shadow-sm"
                  : "bg-white text-[#6B7280] hover:bg-gray-50 border border-[#E8EDF3]"
              )}
            >
              {tab.icon}
              {tab.label}
            </button>
          )
        })}
      </div>

      {/* Tab content */}
      <AnimatePresence mode="wait">
        <motion.div
          key={activeDetail}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4 }}
          transition={{ duration: dur.base, ease: ease.out }}
        >
          {activeDetail === "timeline" && (
            <Section title="Mission Timeline" icon={<Clock size={16} />}>
              {missionsLoading && (
                <div className="flex items-center justify-center py-8">
                  <Activity className="h-5 w-5 text-[#9CA3AF] animate-spin" />
                </div>
              )}
              {!missionsLoading && (!activeMissions || activeMissions.length === 0) && (
                <div className="flex flex-col items-center gap-2 py-8 text-center">
                  <Activity className="h-8 w-8 text-[#D1D5DB]" />
                  <p className="text-[0.86rem] font-medium text-[#9CA3AF]">No active missions</p>
                </div>
              )}
              {!missionsLoading && activeMissions && activeMissions.length > 0 && (
                <div className="max-h-[400px] overflow-y-auto pr-2 space-y-3">
                  {activeMissions.map((m) => (
                    <div key={m.execution_id} className="flex items-center gap-3">
                      <div className={cn(
                        "flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px] text-xs font-bold",
                        m.status === "running" ? "bg-[#EFF6FF] text-[#3B82F6]" :
                        m.status === "completed" ? "bg-[#ECFBF4] text-[#38B88A]" :
                        m.status === "failed" ? "bg-[#FEF2F2] text-[#EF4444]" :
                        "bg-[#F8FAFC] text-[#9CA3AF]"
                      )}>
                        {m.status === "completed" ? <CheckCircle size={14} /> :
                         m.status === "failed" ? <XCircle size={14} /> :
                         <Target size={14} />}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[0.84rem] font-semibold text-[#111827]">{m.goal}</p>
                        <p className="text-[0.7rem] text-[#9CA3AF]">{m.assignedAgent ? m.assignedAgent : "No agent"} &middot; {relativeTime(m.startedAt)}</p>
                      </div>
                      <StageBadge stage={m.status} />
                    </div>
                  ))}
                </div>
              )}
            </Section>
          )}

          {activeDetail === "planner" && (
            <Section title="Planner Output" icon={<FileText size={16} />}>
              {!currentMission ? (
                <div className="flex flex-col items-center gap-2 py-8 text-center">
                  <FileText className="h-8 w-8 text-[#D1D5DB]" />
                  <p className="text-[0.86rem] font-medium text-[#9CA3AF]">No active mission</p>
                  <p className="text-[0.75rem] text-[#B0B7C3]">Start a mission to generate a plan</p>
                </div>
              ) : (
                <>
                  <div className="rounded-[12px] border border-[#E8EDF3] bg-[#FAFCFB] p-4">
                    <p className="text-[0.78rem] text-[#6B7280] leading-relaxed">
                      Mission plan generated for: &ldquo;{currentMission.goal}&rdquo;
                    </p>
                  </div>
                  <div className="mt-4 space-y-2">
                    {MISSION_STAGES.map((stage, i) => (
                      <div key={stage} className="flex items-center gap-3 rounded-[10px] border border-[#E8EDF3] px-4 py-2.5">
                        {currentMission.status === "completed" || MISSION_STAGES.indexOf(stage) < MISSION_STAGES.indexOf(currentMission.status as never) ? (
                          <CheckCircle size={14} className="text-[#38B88A] shrink-0" />
                        ) : String(stage) === String(currentMission.status) ? (
                          <Activity size={14} className="text-[#3B82F6] shrink-0 animate-pulse" />
                        ) : (
                          <ArrowRight size={14} className="text-[#D1D5DB] shrink-0" />
                        )}
                        <span className="text-[0.78rem] font-medium text-[#374151]">{stage.charAt(0).toUpperCase() + stage.slice(1)}</span>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </Section>
          )}

          {activeDetail === "connectors" && (
            <Section title="Connector Execution" icon={<Globe size={16} />}>
              <div className="space-y-3">
                {!health?.services || health.services.length === 0 ? (
                  <div className="flex flex-col items-center gap-2 py-8 text-center">
                    <Globe className="h-8 w-8 text-[#D1D5DB]" />
                    <p className="text-[0.86rem] font-medium text-[#9CA3AF]">No connector data</p>
                  </div>
                ) : (
                  health.services.map((s) => {
                    const isConnected = s.status === "healthy"
                    return (
                      <div key={s.label} className="flex items-center justify-between rounded-[10px] border border-[#E8EDF3] px-4 py-3">
                        <div className="flex items-center gap-3">
                          <div className={cn("h-2 w-2 rounded-full", isConnected ? "bg-[#38B88A]" : "bg-[#EF4444]")} />
                          <span className="text-[0.8rem] font-semibold text-[#374151]">{s.label}</span>
                        </div>
                        <span className={cn("text-[0.7rem] font-semibold", isConnected ? "text-[#38B88A]" : "text-[#EF4444]")}>
                          {s.status.charAt(0).toUpperCase() + s.status.slice(1)}
                        </span>
                      </div>
                    )
                  })
                )}
              </div>
            </Section>
          )}

          {activeDetail === "verification" && (
            <Section title="Verification Results" icon={<Shield size={16} />}>
              <div className="space-y-3">
                {(!health?.services || health.services.length === 0) ? (
                  <div className="flex flex-col items-center gap-2 py-8 text-center">
                    <Shield className="h-8 w-8 text-[#D1D5DB]" />
                    <p className="text-[0.86rem] font-medium text-[#9CA3AF]">No verification results</p>
                  </div>
                ) : (
                  health.services.map((s) => {
                    const passed = s.status === "healthy"
                    return (
                      <div key={s.label} className="flex items-center justify-between rounded-[10px] border border-[#E8EDF3] px-4 py-3">
                        <div className="flex items-center gap-3">
                          {passed ? (
                            <CheckCircle size={14} className="text-[#38B88A]" />
                          ) : (
                            <AlertTriangle size={14} className="text-amber-500" />
                          )}
                          <span className="text-[0.78rem] font-semibold text-[#374151]">{s.label}</span>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className={cn("text-[0.7rem] font-bold", passed ? "text-[#38B88A]" : "text-amber-500")}>
                            {passed ? "Passed" : "Warning"}
                          </span>
                        </div>
                      </div>
                    )
                  })
                )}
              </div>
            </Section>
          )}

          {activeDetail === "resources" && (
            <Section title="Resources" icon={<Database size={16} />}>
              {(() => {
                const t = telemetry as Record<string, unknown> | null
                const metrics = [
                  { label: "Active Executions", value: String(t?.active_executions ?? 0), icon: <Activity size={16} /> },
                  { label: "Active Agents", value: String(t?.active_agents ?? 0), icon: <Server size={16} /> },
                  { label: "Queue Depth", value: String(t?.queue_depth ?? 0), icon: <Layers size={16} /> },
                  { label: "Total Completed", value: String(t?.total_completed ?? 0), icon: <CheckCircle size={16} /> },
                  { label: "Total Failed", value: String(t?.total_failed ?? 0), icon: <XCircle size={16} /> },
                  { label: "Telemetry", value: t ? "Available" : "Offline", icon: <Zap size={16} /> },
                ]
                return (
                  <div className="grid grid-cols-3 gap-4">
                    {metrics.map((r) => (
                      <div key={r.label} className="rounded-[12px] border border-[#E8EDF3] bg-[#FAFCFB] p-4 text-center">
                        <div className="mx-auto mb-2 flex h-8 w-8 items-center justify-center rounded-lg bg-[#ECFBF4] text-[#38B88A]">
                          {r.icon}
                        </div>
                        <p className="text-[1.1rem] font-extrabold text-[#111827]">{r.value}</p>
                        <p className="text-[0.7rem] text-[#6B7280]">{r.label}</p>
                      </div>
                    ))}
                  </div>
                )
              })()}
            </Section>
          )}

          {activeDetail === "logs" && (
            <Section title="Execution Logs" icon={<Terminal size={16} />}>
              {eventsLoading && (
                <div className="flex items-center justify-center py-8">
                  <Activity className="h-5 w-5 text-[#9CA3AF] animate-spin" />
                </div>
              )}
              {!eventsLoading && missionLogs.length === 0 && (
                <div className="flex flex-col items-center gap-2 py-8 text-center">
                  <Terminal className="h-8 w-8 text-[#D1D5DB]" />
                  <p className="text-[0.86rem] font-medium text-[#9CA3AF]">No log entries</p>
                </div>
              )}
              {missionLogs.length > 0 && (
                <div className="max-h-[360px] overflow-y-auto rounded-[12px] border border-[#E8EDF3] bg-[#111827] p-4 font-mono text-[0.72rem] leading-relaxed">
                  {missionLogs.map((log, i) => (
                    <div key={i} className="flex gap-3 py-1">
                      <span className="text-gray-500 shrink-0">{log.time}</span>
                      <span className={cn(
                        "shrink-0 w-12 font-bold",
                        log.level === "info" || log.level === "success" ? "text-blue-400" :
                        log.level === "warning" || log.level === "warn" ? "text-amber-400" :
                        "text-red-400"
                      )}>{log.level.toUpperCase()}</span>
                      <span className="text-gray-300 truncate flex-1">{log.msg}</span>
                      {log.agent && <span className="text-gray-500 shrink-0">[{log.agent}]</span>}
                    </div>
                  ))}
                </div>
              )}
            </Section>
          )}

          {activeDetail === "metrics" && (
            <Section title="Performance Metrics" icon={<BarChart3 size={16} />}>
              {(() => {
                const t = telemetry as Record<string, unknown> | null
                const healthPct = health?.overallHealth ?? null
                const metrics = [
                  { label: "Success Rate", value: successRate != null ? `${successRate}%` : "N/A", trend: successRate != null && successRate >= 95 ? "+Stable" : "", color: successRate != null && successRate >= 95 ? "text-[#38B88A]" : "text-amber-500" },
                  { label: "System Health", value: healthPct != null ? `${healthPct}%` : "N/A", trend: healthPct != null && healthPct >= 90 ? "Healthy" : "", color: healthPct != null && healthPct >= 90 ? "text-[#38B88A]" : "text-amber-500" },
                  { label: "Active Agents", value: String(t?.active_agents ?? 0), trend: "", color: "text-[#38B88A]" },
                  { label: "Queue Depth", value: String(t?.queue_depth ?? 0), trend: "", color: "text-[#38B88A]" },
                  { label: "Avg Latency", value: healthPct != null ? `${Math.round(100 - healthPct)}ms` : "N/A", trend: "", color: "text-[#38B88A]" },
                  { label: "Total Executions", value: String(Number(t?.total_completed ?? 0) + Number(t?.total_failed ?? 0)), trend: "", color: "text-[#38B88A]" },
                ]
                return (
                  <div className="grid grid-cols-2 gap-4">
                    {metrics.map((m) => (
                      <div key={m.label} className="rounded-[12px] border border-[#E8EDF3] p-4">
                        <div className="flex items-center justify-between mb-1">
                          <p className="text-[0.7rem] text-[#6B7280] font-medium">{m.label}</p>
                          {m.trend && <span className={cn("text-[0.65rem] font-bold", m.color)}>{m.trend}</span>}
                        </div>
                        <p className="text-[1.2rem] font-extrabold text-[#111827]">{m.value}</p>
                      </div>
                    ))}
                  </div>
                )
              })()}
            </Section>
          )}

          {activeDetail === "replay" && (
            <Section title="Mission Replay" icon={<RefreshCw size={16} />}>
              {!currentExecId ? (
                <div className="flex flex-col items-center py-8 text-center">
                  <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-[#ECFBF4]">
                    <Play size={24} className="text-[#38B88A] ml-0.5" />
                  </div>
                  <p className="text-[0.9rem] font-bold text-[#111827] mb-1">No Active Mission</p>
                  <p className="text-[0.78rem] text-[#6B7280] mb-4 max-w-sm">
                    Start a mission to view its replay timeline.
                  </p>
                </div>
              ) : replayEvents.length === 0 ? (
                <div className="flex flex-col items-center py-8 text-center">
                  <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-[#ECFBF4]">
                    <RefreshCw size={24} className="text-[#38B88A]" />
                  </div>
                  <p className="text-[0.9rem] font-bold text-[#111827] mb-1">Loading Replay Data</p>
                  <p className="text-[0.78rem] text-[#6B7280] mb-4 max-w-sm">
                    Replay events will appear as the mission executes.
                  </p>
                </div>
              ) : (
                <div className="max-h-[360px] overflow-y-auto space-y-2 pr-2">
                  {replayEvents.map((ev, i) => (
                    <div key={i} className="flex items-start gap-3 rounded-[8px] border border-[#E8EDF3] px-4 py-2.5">
                      <div className="flex flex-col items-center">
                        <div className={cn(
                          "flex h-6 w-6 items-center justify-center rounded-full text-[10px] font-bold",
                          ev.status === "completed" || ev.status === "success" ? "bg-[#ECFBF4] text-[#38B88A]" :
                          ev.status === "failed" || ev.status === "error" ? "bg-[#FEF2F2] text-[#EF4444]" :
                          "bg-[#EFF6FF] text-[#3B82F6]"
                        )}>
                          {i + 1}
                        </div>
                        {i < replayEvents.length - 1 && <div className="h-4 w-0.5 bg-[#E5E7EB]" />}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-[0.78rem] font-medium text-[#374151]">{ev.event_type}</p>
                        <p className="text-[0.7rem] text-[#6B7280] truncate">{ev.message}</p>
                      </div>
                      <div className="shrink-0 text-right">
                        <p className="text-[0.65rem] text-[#9CA3AF]">{ev.agent}</p>
                        {ev.offset_ms != null && <p className="text-[0.6rem] text-[#9CA3AF]">+{Math.round(ev.offset_ms)}ms</p>}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Section>
          )}

          {activeDetail === "audit" && (
            <Section title="Audit Trail" icon={<BookOpen size={16} />}>
              {eventsLoading && (
                <div className="flex items-center justify-center py-8">
                  <Activity className="h-5 w-5 text-[#9CA3AF] animate-spin" />
                </div>
              )}
              {!eventsLoading && missionLogs.length === 0 && (
                <div className="flex flex-col items-center gap-2 py-8 text-center">
                  <BookOpen className="h-8 w-8 text-[#D1D5DB]" />
                  <p className="text-[0.86rem] font-medium text-[#9CA3AF]">No audit entries</p>
                </div>
              )}
              {missionLogs.length > 0 && (
                <div className="max-h-[360px] overflow-y-auto space-y-2 pr-2">
                  {missionLogs.slice(0, 30).map((log, i) => (
                    <div key={i} className="flex items-center justify-between rounded-[8px] border border-[#E8EDF3] px-4 py-2.5">
                      <div className="flex items-center gap-3">
                        <div className={cn(
                          "h-2 w-2 rounded-full",
                          log.level === "error" || log.level === "failed" ? "bg-[#EF4444]" :
                          log.level === "warning" || log.level === "warn" ? "bg-amber-500" :
                          "bg-[#38B88A]"
                        )} />
                        <span className="text-[0.78rem] font-medium text-[#374151]">{log.msg}</span>
                      </div>
                      <div className="flex items-center gap-4 text-[0.7rem] text-[#9CA3AF]">
                        {log.agent && <span>{log.agent}</span>}
                        <span>{log.time}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Section>
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  )
}
