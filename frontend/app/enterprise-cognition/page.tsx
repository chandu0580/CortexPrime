"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import CortexShell from "@/components/layout/CortexShell"
import { stagger, variants } from "@/lib/motion-tokens"
import { useCognitionDashboard, useCognitionStatus, useCognitionTimeline, useCognitionHealth, useStartCognition, useStopCognition, usePauseCognition, useResumeCognition } from "@/hooks/queries/enterprise/useEnterpriseCognition"
import { Loader2, BrainCircuit, Activity, AlertTriangle, CheckCircle2, GitBranch, Server, TrendingUp, TrendingDown, Clock, Shield, Play, Square, Pause, PlayCircle, Eye, ArrowUp, ArrowDown, Minus, Database, Cpu, BarChart2, Layers, FileText, Zap } from "lucide-react"
import { PageLoading, PageError, PageEmpty } from "@/app/loading-states"

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    running: "bg-[#F0FDF4] text-[#38B88A]",
    stopped: "bg-gray-100 text-gray-500",
    paused: "bg-amber-50 text-amber-600",
    error: "bg-red-50 text-red-600",
  }
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[0.7rem] font-medium ${colors[status] || "bg-gray-100 text-gray-500"}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${status === "running" ? "bg-[#38B88A] animate-pulse" : status === "error" ? "bg-red-500" : "bg-gray-400"}`} />
      {status}
    </span>
  )
}

function PhaseBadge({ phase }: { phase: string }) {
  const labels: Record<string, string> = {
    idle: "Idle",
    repository_monitoring: "Monitoring Repos",
    context_refresh: "Refreshing Context",
    risk_re_evaluation: "Evaluating Risk",
    prediction_refresh: "Refreshing Predictions",
    infrastructure_awareness: "Checking Infrastructure",
    knowledge_evolution: "Evolving Knowledge",
    executive_notification: "Notifying Executive",
  }
  return (
    <span className="rounded bg-[#EFF6FF] px-2 py-0.5 text-[0.65rem] font-medium text-blue-600">
      {labels[phase] || phase}
    </span>
  )
}

function ConfidenceBar({ confidence }: { confidence: number }) {
  const pct = Math.round(confidence * 100)
  const color = pct >= 80 ? "bg-[#38B88A]" : pct >= 50 ? "bg-amber-400" : "bg-red-400"
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-gray-100">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[0.6rem] font-medium text-[#6B7280]">{pct}%</span>
    </div>
  )
}

function TriggerActionBadge({ action }: { action: string }) {
  const labels: Record<string, string> = {
    context_refresh: "Context Refresh",
    risk_assessment: "Risk Assessment",
    risk_re_evaluation: "Risk Re-eval",
    prediction_refresh: "Prediction Refresh",
    executive_notification: "Executive Notify",
  }
  return (
    <span className="rounded bg-[#F0FDF4] px-1.5 py-0.5 text-[0.6rem] font-medium text-[#38B88A]">
      {labels[action] || action}
    </span>
  )
}

function ChangeTypeIcon({ type }: { type: string }) {
  const icons: Record<string, React.ElementType> = {
    repository_added: GitBranch,
    repository_removed: GitBranch,
    architecture_changed: Layers,
    architecture_drift: AlertTriangle,
    ownership_changed: Shield,
    risk_changed: TrendingUp,
    context_refreshed: Eye,
    prediction_refreshed: BarChart2,
    kubernetes_health_changed: Server,
    argocd_sync_drift: GitBranch,
    prometheus_alerts_firing: AlertTriangle,
    loki_error_spike: FileText,
    otel_service_degradation: Cpu,
    executive_mission_created: Zap,
  }
  const Icon = icons[type] || Activity
  return <Icon className="h-3.5 w-3.5 text-[#6B7280]" />
}

function TimelineEntryCard({ entry }: { entry: any }) {
  const Icon = ChangeTypeIcon({ type: entry.change_type })
  const riskChanged = entry.risk_before !== null && entry.risk_after !== null

  return (
    <div className="rounded-lg border border-[#E8EDF3] bg-white p-3 transition-all hover:border-[#38B88A]/20">
      <div className="flex items-start gap-3">
        <div className="mt-0.5 shrink-0 rounded-md bg-[#F4F7FA] p-1.5">
          {Icon}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-[0.65rem] font-medium uppercase tracking-wider text-[#9CA3AF]">{entry.change_type.replace(/_/g, " ")}</span>
            <PhaseBadge phase={entry.phase} />
          </div>
          <p className="mt-0.5 text-sm font-medium text-[#111827]">{entry.reason}</p>

          <div className="mt-1.5 flex flex-wrap items-center gap-2">
            <span className="text-[0.65rem] text-[#6B7280]">
              <Clock className="mr-0.5 inline h-3 w-3" />
              {new Date(entry.timestamp).toLocaleString()}
            </span>
            <ConfidenceBar confidence={entry.confidence} />
          </div>

          {riskChanged && (
            <div className="mt-1.5 flex items-center gap-2 text-[0.7rem] text-[#6B7280]">
              <span>Risk:</span>
              <span className="font-medium text-[#38B88A]">{entry.risk_before?.toFixed(1)}</span>
              {(entry.risk_after ?? 0) > (entry.risk_before ?? 0)
                ? <TrendingUp className="h-3 w-3 text-red-500" />
                : (entry.risk_after ?? 0) < (entry.risk_before ?? 0)
                  ? <TrendingDown className="h-3 w-3 text-[#38B88A]" />
                  : <Minus className="h-3 w-3 text-gray-400" />
              }
              <span className="font-medium text-[#111827]">{entry.risk_after?.toFixed(1)}</span>
            </div>
          )}

          {entry.triggered_actions && entry.triggered_actions.length > 0 && (
            <div className="mt-1.5 flex flex-wrap gap-1">
              {entry.triggered_actions.map((action: string, i: number) => (
                <TriggerActionBadge key={i} action={action} />
              ))}
            </div>
          )}

          {entry.affected_repositories && entry.affected_repositories.length > 0 && (
            <div className="mt-1.5 flex flex-wrap gap-1 text-[0.6rem] text-[#6B7280]">
              {entry.affected_repositories.map((r: string, i: number) => (
                <span key={i} className="rounded bg-[#F4F7FA] px-1.5 py-0.5">{r}</span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default function EnterpriseCognitionCenter() {
  const { data: status, isLoading: statusLoading } = useCognitionStatus()
  const { data: dashboard, isLoading: dashLoading } = useCognitionDashboard()
  const { data: timeline, isLoading: timelineLoading } = useCognitionTimeline(50)
  const { data: health, isLoading: healthLoading } = useCognitionHealth()
  const startMutation = useStartCognition()
  const stopMutation = useStopCognition()
  const pauseMutation = usePauseCognition()
  const resumeMutation = useResumeCognition()

  const [filterType, setFilterType] = useState<string>("")

  const isLoading = statusLoading || dashLoading

  if (isLoading) return <CortexShell title="Enterprise Cognition Center" subtitle="Continuous Engineering Reasoning Loop"><PageLoading /></CortexShell>
  if (!dashboard) return <CortexShell title="Enterprise Cognition Center" subtitle="Continuous Engineering Reasoning Loop"><PageError message="Failed to load cognition data" /></CortexShell>

  const s = dashboard.status
  const isRunning = s.state === "running"

  const filteredTimeline = filterType
    ? (timeline ?? []).filter((e: any) => e.change_type === filterType)
    : (timeline ?? [])

  const statCards = [
    { label: "Loop Cycles", value: s.loop_count, icon: Activity, color: "text-[#38B88A]" },
    { label: "Repos Tracked", value: s.known_repositories_count, icon: GitBranch, color: "text-blue-500" },
    { label: "Services Tracked", value: s.known_services_count, icon: Server, color: "text-purple-500" },
    { label: "Timeline Entries", value: s.timeline_entries_count, icon: Clock, color: "text-amber-500" },
  ]

  const recentRiskChanges = dashboard.risk_evolution
    .filter((r: any) => r.score > 50)
    .slice(0, 10)

  const changeTypes = ["", "architecture_changed", "architecture_drift", "risk_changed", "repository_added", "repository_removed", "kubernetes_health_changed", "prometheus_alerts_firing", "loki_error_spike", "executive_mission_created"]

  return (
    <CortexShell title="Enterprise Cognition Center" subtitle="Continuous Engineering Reasoning Loop">
      <div className="relative z-10 mx-auto max-w-7xl space-y-6">
        {/* Controls */}
        <motion.div initial="hidden" animate="visible" variants={stagger(0.04, 0.01)} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#E8EDF3] bg-white p-4">
          <div className="flex items-center gap-3">
            <BrainCircuit className="h-5 w-5 text-[#38B88A]" />
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-bold text-[#111827]">Cognition Loop</h2>
                <StatusBadge status={s.state} />
                <PhaseBadge phase={s.current_phase} />
              </div>
              <p className="text-[0.7rem] text-[#6B7280]">
                Interval: {s.loop_interval_seconds}s · Repo: {s.repo_interval_seconds}s · Infra: {s.infra_interval_seconds}s
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {isRunning ? (
              <>
                <button
                  onClick={() => pauseMutation.mutate()}
                  disabled={pauseMutation.isPending}
                  className="flex items-center gap-1.5 rounded-lg border border-amber-200 bg-amber-50 px-3 py-1.5 text-[0.7rem] font-medium text-amber-700 transition-colors hover:bg-amber-100"
                >
                  <Pause className="h-3.5 w-3.5" />
                  Pause
                </button>
                <button
                  onClick={() => stopMutation.mutate()}
                  disabled={stopMutation.isPending}
                  className="flex items-center gap-1.5 rounded-lg border border-red-200 bg-red-50 px-3 py-1.5 text-[0.7rem] font-medium text-red-700 transition-colors hover:bg-red-100"
                >
                  <Square className="h-3.5 w-3.5" />
                  Stop
                </button>
              </>
            ) : (
              <button
                onClick={() => startMutation.mutate(undefined)}
                disabled={startMutation.isPending}
                className="flex items-center gap-1.5 rounded-lg border border-[#38B88A]/30 bg-[#F0FDF4] px-3 py-1.5 text-[0.7rem] font-medium text-[#38B88A] transition-colors hover:bg-[#E6F7EE]"
              >
                <Play className="h-3.5 w-3.5" />
                Start
              </button>
            )}
            {s.state === "paused" && (
              <button
                onClick={() => resumeMutation.mutate()}
                disabled={resumeMutation.isPending}
                className="flex items-center gap-1.5 rounded-lg border border-blue-200 bg-blue-50 px-3 py-1.5 text-[0.7rem] font-medium text-blue-700 transition-colors hover:bg-blue-100"
              >
                <PlayCircle className="h-3.5 w-3.5" />
                Resume
              </button>
            )}
          </div>
        </motion.div>

        {/* Stat Cards */}
        <motion.div initial="hidden" animate="visible" variants={stagger(0.04, 0.02)} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {statCards.map((stat, i) => {
            const Icon = stat.icon
            return (
              <motion.div key={i} variants={variants.fadeUp} className="rounded-xl border border-[#E8EDF3] bg-white p-4">
                <div className="flex items-center gap-2">
                  <Icon className={`h-4 w-4 ${stat.color}`} />
                  <span className="text-[0.7rem] font-medium text-[#6B7280]">{stat.label}</span>
                </div>
                <p className="mt-1.5 text-2xl font-bold text-[#111827]">{stat.value}</p>
              </motion.div>
            )
          })}
        </motion.div>

        {/* Main Grid: Latest Observations + Risk Evolution */}
        <motion.div initial="hidden" animate="visible" variants={stagger(0.05, 0.03)} className="grid gap-5 lg:grid-cols-2">
          {/* Latest Observations */}
          <motion.div variants={variants.fadeUp} className="rounded-xl border border-[#E8EDF3] bg-white p-5">
            <div className="mb-4 flex items-center gap-2">
              <Eye className="h-4 w-4 text-[#38B88A]" />
              <h2 className="text-sm font-bold text-[#111827]">Latest Observations</h2>
            </div>
            <div className="max-h-80 space-y-2 overflow-y-auto">
              {dashboard.latest_observations.length === 0 ? (
                <p className="py-6 text-center text-[0.78rem] text-[#9CA3AF]">No observations yet</p>
              ) : (
                dashboard.latest_observations.slice(0, 10).map((obs: any, i: number) => (
                  <div key={i} className="rounded-lg border border-[#E8EDF3] bg-[#FAFBFC] p-3">
                    <div className="flex items-center gap-2">
                      <ChangeTypeIcon type={obs.type} />
                      <span className="text-[0.65rem] font-medium uppercase tracking-wider text-[#9CA3AF]">{obs.type.replace(/_/g, " ")}</span>
                      <ConfidenceBar confidence={obs.confidence} />
                    </div>
                    <p className="mt-1 text-[0.78rem] text-[#111827]">{obs.reason}</p>
                    <div className="mt-1 flex items-center gap-2 text-[0.65rem] text-[#6B7280]">
                      <Clock className="h-3 w-3" />
                      {new Date(obs.timestamp).toLocaleString()}
                    </div>
                    {obs.repositories && obs.repositories.length > 0 && (
                      <div className="mt-1 flex flex-wrap gap-1">
                        {obs.repositories.map((r: string, j: number) => (
                          <span key={j} className="rounded bg-[#F0FDF4] px-1.5 py-0.5 text-[0.6rem] font-medium text-[#38B88A]">{r}</span>
                        ))}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </motion.div>

          {/* Risk Evolution */}
          <motion.div variants={variants.fadeUp} className="rounded-xl border border-[#E8EDF3] bg-white p-5">
            <div className="mb-4 flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-[#38B88A]" />
              <h2 className="text-sm font-bold text-[#111827]">Risk Evolution</h2>
            </div>
            <div className="space-y-2">
              {dashboard.risk_evolution.length === 0 ? (
                <p className="py-6 text-center text-[0.78rem] text-[#9CA3AF]">No risk data yet</p>
              ) : (
                dashboard.risk_evolution.map((risk: any, i: number) => (
                  <div key={i} className="flex items-center gap-3 rounded-lg border border-[#E8EDF3] bg-[#FAFBFC] px-3.5 py-2.5">
                    <div className={`h-2 w-2 rounded-full ${risk.score > 70 ? "bg-red-500" : risk.score > 40 ? "bg-amber-400" : "bg-[#38B88A]"}`} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-[#111827]">{risk.repository}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-gray-100">
                        <div
                          className={`h-full rounded-full ${risk.score > 70 ? "bg-red-500" : risk.score > 40 ? "bg-amber-400" : "bg-[#38B88A]"}`}
                          style={{ width: `${risk.score}%` }}
                        />
                      </div>
                      <span className="shrink-0 text-[0.7rem] font-bold text-[#111827]">{risk.score.toFixed(0)}</span>
                    </div>
                  </div>
                ))
              )}
            </div>

            {recentRiskChanges.length > 0 && (
              <div className="mt-4">
                <h3 className="mb-2 text-[0.7rem] font-semibold uppercase tracking-wider text-[#9CA3AF]">High Risk Repositories ({recentRiskChanges.length})</h3>
                <div className="space-y-1.5">
                  {recentRiskChanges.map((risk: any, i: number) => (
                    <div key={i} className="flex items-center gap-2 rounded-md bg-red-50 px-2.5 py-1.5 text-[0.7rem]">
                      <AlertTriangle className="h-3 w-3 shrink-0 text-red-500" />
                      <span className="font-medium text-red-700">{risk.repository}</span>
                      <span className="ml-auto font-bold text-red-600">{risk.score.toFixed(0)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        </motion.div>

        {/* Architecture Changes */}
        {dashboard.architecture_changes && dashboard.architecture_changes.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="rounded-xl border border-[#E8EDF3] bg-white p-5"
          >
            <div className="mb-4 flex items-center gap-2">
              <Layers className="h-4 w-4 text-[#38B88A]" />
              <h2 className="text-sm font-bold text-[#111827]">Architecture Changes</h2>
              <span className="ml-auto rounded bg-[#F4F7FA] px-2 py-0.5 text-[0.65rem] text-[#6B7280]">{dashboard.architecture_changes.length} recent</span>
            </div>
            <div className="space-y-2">
              {dashboard.architecture_changes.map((change: any, i: number) => (
                <div key={i} className="flex items-center gap-3 rounded-lg border border-[#E8EDF3] bg-[#FAFBFC] px-3.5 py-2.5">
                  {change.type === "architecture_drift" ? (
                    <AlertTriangle className="h-4 w-4 shrink-0 text-amber-500" />
                  ) : (
                    <Layers className="h-4 w-4 shrink-0 text-blue-500" />
                  )}
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-[#111827]">{change.repository}</p>
                    <p className="text-[0.7rem] text-[#6B7280]">{change.reason}</p>
                  </div>
                  <span className="shrink-0 text-[0.65rem] text-[#9CA3AF]">{new Date(change.timestamp).toLocaleString()}</span>
                </div>
              ))}
            </div>
          </motion.div>
        )}

        {/* Timeline */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="rounded-xl border border-[#E8EDF3] bg-white p-5"
        >
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-[#38B88A]" />
              <h2 className="text-sm font-bold text-[#111827]">Cognition Timeline</h2>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {changeTypes.map((type) => (
                <button
                  key={type}
                  onClick={() => setFilterType(filterType === type ? "" : type)}
                  className={`rounded-full px-2.5 py-1 text-[0.6rem] font-medium transition-all ${
                    filterType === type
                      ? "bg-[#38B88A] text-white"
                      : "bg-[#F4F7FA] text-[#6B7280] hover:bg-[#E8EDF3]"
                  }`}
                >
                  {type ? type.replace(/_/g, " ") : "All"}
                </button>
              ))}
            </div>
          </div>

          {timelineLoading ? (
            <div className="flex items-center justify-center py-8 text-[0.78rem] text-[#6B7280]">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Loading timeline...
            </div>
          ) : filteredTimeline.length === 0 ? (
            <p className="py-6 text-center text-[0.78rem] text-[#9CA3AF]">No timeline entries</p>
          ) : (
            <div className="max-h-96 space-y-2 overflow-y-auto">
              {filteredTimeline.map((entry: any, i: number) => (
                <TimelineEntryCard key={entry.entry_id || i} entry={entry} />
              ))}
            </div>
          )}
        </motion.div>

        {/* Health */}
        {health && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="rounded-xl border border-[#E8EDF3] bg-white p-5"
          >
            <div className="mb-4 flex items-center gap-2">
              <Shield className="h-4 w-4 text-[#38B88A]" />
              <h2 className="text-sm font-bold text-[#111827]">Cognition Source Health</h2>
              <span className={`ml-auto rounded-full px-2.5 py-0.5 text-[0.65rem] font-medium ${
                health.status === "healthy"
                  ? "bg-[#F0FDF4] text-[#38B88A]"
                  : "bg-amber-50 text-amber-600"
              }`}>
                {health.available_sources}/{health.total_sources} available
              </span>
            </div>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {Object.entries(health.sources).map(([name, available]) => (
                <div key={name} className="flex items-center gap-2 rounded-lg border border-[#E8EDF3] bg-[#FAFBFC] px-3 py-2">
                  {available ? (
                    <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-[#38B88A]" />
                  ) : (
                    <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-amber-500" />
                  )}
                  <span className="text-[0.7rem] font-medium text-[#111827]">{name}</span>
                </div>
              ))}
            </div>
          </motion.div>
        )}

        {/* Infrastructure Health Baseline */}
        {dashboard.infra_health_baseline && Object.keys(dashboard.infra_health_baseline).length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
            className="rounded-xl border border-[#E8EDF3] bg-white p-5"
          >
            <div className="mb-4 flex items-center gap-2">
              <Server className="h-4 w-4 text-[#38B88A]" />
              <h2 className="text-sm font-bold text-[#111827]">Infrastructure Health Baseline</h2>
            </div>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {Object.entries(dashboard.infra_health_baseline).map(([name, status]) => (
                <div key={name} className="flex items-center gap-2 rounded-lg border border-[#E8EDF3] bg-[#FAFBFC] px-3 py-2">
                  <span className={`h-2 w-2 rounded-full ${
                    String(status) === "healthy" ? "bg-[#38B88A]" :
                    String(status) === "degraded" ? "bg-amber-400" :
                    "bg-red-500"
                  }`} />
                  <span className="text-[0.7rem] font-medium capitalize text-[#111827]">{name}</span>
                  <span className="ml-auto text-[0.65rem] text-[#6B7280]">{String(status)}</span>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </div>
    </CortexShell>
  )
}
