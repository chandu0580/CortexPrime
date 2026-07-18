"use client"

import { useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Eye, Activity, AlertTriangle, CheckCircle, Loader2,
  TrendingUp, TrendingDown, Minus, Bell, X,
  Wifi, Server, Zap, Globe,
} from "lucide-react"
import { useObservationStore, type ObservationMetric, type ObservationAlert } from "@/store/observationStore"
import { useMissionStore } from "@/store/missionStore"
import { useRuntimeStore } from "@/store/runtimeStore"
import { cn } from "@/utils/cn"
import { dur, ease } from "@/lib/motion-tokens"

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  connector_health: <Globe size={14} />,
  mission_progress: <Activity size={14} />,
  workflow_execution: <Zap size={14} />,
  runtime_metrics: <Server size={14} />,
}

const STATUS_COLORS: Record<string, string> = {
  healthy: "text-emerald-600 bg-emerald-50 border-emerald-200",
  warning: "text-amber-600 bg-amber-50 border-amber-200",
  critical: "text-red-600 bg-red-50 border-red-200",
}

const TREND_ICONS: Record<string, React.ReactNode> = {
  up: <TrendingUp size={10} className="text-emerald-500" />,
  down: <TrendingDown size={10} className="text-red-500" />,
  stable: <Minus size={10} className="text-gray-400" />,
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: "border-red-200 bg-red-50",
  warning: "border-amber-200 bg-amber-50",
  info: "border-blue-200 bg-blue-50",
}

const SEVERITY_DOTS: Record<string, string> = {
  critical: "bg-red-500",
  warning: "bg-amber-500",
  info: "bg-blue-500",
}

function MetricRow({ metric }: { metric: ObservationMetric }) {
  return (
    <div className="flex items-center justify-between rounded-[6px] px-2 py-1.5 hover:bg-gray-50">
      <div className="flex items-center gap-2">
        <span className={cn(
          "h-1.5 w-1.5 rounded-full",
          metric.status === "healthy" ? "bg-[#38B88A]" :
          metric.status === "warning" ? "bg-amber-500" : "bg-red-500"
        )} />
        <span className="text-[0.72rem] text-[#374151]">{metric.label}</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-[0.72rem] font-semibold text-[#111827] font-mono">{metric.value}</span>
        {TREND_ICONS[metric.trend]}
      </div>
    </div>
  )
}

function AlertItem({ alert, onDismiss }: { alert: ObservationAlert; onDismiss: (id: string) => void }) {
  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: "auto" }}
      exit={{ opacity: 0, height: 0 }}
      className={cn(
        "flex items-start gap-2.5 rounded-[8px] border px-3 py-2",
        SEVERITY_COLORS[alert.severity],
        alert.acknowledged && "opacity-60"
      )}
    >
      <div className={cn("mt-1 h-2 w-2 rounded-full shrink-0", SEVERITY_DOTS[alert.severity])} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-[0.7rem] font-bold uppercase tracking-wider text-[#374151]">{alert.source}</span>
          {!alert.acknowledged && (
            <span className="rounded bg-white/60 px-1 py-0.5 text-[9px] font-bold text-amber-600">NEW</span>
          )}
        </div>
        <p className="text-[0.72rem] text-[#6B7280] mt-0.5">{alert.message}</p>
      </div>
      <button
        onClick={() => onDismiss(alert.id)}
        className="shrink-0 rounded p-0.5 text-gray-400 hover:text-gray-600 hover:bg-white/50"
      >
        <X size={12} />
      </button>
    </motion.div>
  )
}

export function ObservationEngine() {
  const missionStage = useMissionStore((s) => s.stage)
  const runtimeStatus = useRuntimeStore((s) => s.runtimeStatus)
  const {
    categories, alerts, isObserving, lastUpdate,
    setMetrics, addAlert, acknowledgeAlert, dismissAlert, setObserving,
  } = useObservationStore()

  useEffect(() => {
    setObserving(true)
    return () => setObserving(false)
  }, [setObserving])

  const alertCount = alerts.filter((a) => !a.acknowledged).length
  const criticalCount = alerts.filter((a) => a.severity === "critical" && !a.acknowledged).length

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Eye size={16} className="text-[#38B88A]" />
          <h3 className="text-[0.9rem] font-bold text-[#111827]">Observation Engine</h3>
          {isObserving && (
            <span className="flex items-center gap-1 text-[10px] text-[#38B88A] font-semibold">
              <span className="h-1.5 w-1.5 rounded-full bg-[#38B88A] animate-pulse" />
              Live
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {criticalCount > 0 && (
            <span className="flex items-center gap-1 rounded-full bg-red-50 px-2 py-0.5 text-[10px] font-bold text-red-600 border border-red-200">
              <AlertTriangle size={10} />
              {criticalCount} critical
            </span>
          )}
          {lastUpdate && (
            <span className="text-[10px] text-[#9CA3AF]">
              {new Date(lastUpdate).toLocaleTimeString()}
            </span>
          )}
        </div>
      </div>

      {/* Alerts bar */}
      {alertCount > 0 && (
        <div className="space-y-1.5">
          <div className="flex items-center gap-1.5">
            <Bell size={12} className="text-amber-500" />
            <span className="text-[0.72rem] font-semibold text-[#374151]">Active Alerts ({alertCount})</span>
          </div>
          <AnimatePresence>
            {alerts.filter((a) => !a.acknowledged).slice(0, 5).map((alert) => (
              <AlertItem key={alert.id} alert={alert} onDismiss={dismissAlert} />
            ))}
          </AnimatePresence>
        </div>
      )}

      {/* Metric categories */}
      <div className="grid grid-cols-2 gap-3">
        {categories.map((cat) => (
          <div
            key={cat.id}
            className="rounded-[10px] border border-[#E8EDF3] bg-white p-3"
          >
            <div className="mb-2 flex items-center gap-2">
              <span className="text-[#38B88A]">{CATEGORY_ICONS[cat.id]}</span>
              <span className="text-[0.72rem] font-bold text-[#374151]">{cat.label}</span>
              {cat.alerts.length > 0 && (
                <span className="ml-auto rounded-full bg-amber-50 px-1.5 py-0.5 text-[9px] font-bold text-amber-600">
                  {cat.alerts.length}
                </span>
              )}
            </div>
            <div className="space-y-0.5">
              {cat.metrics.length === 0 && (
                <p className="text-[0.7rem] text-[#9CA3AF] py-2 text-center">No metrics yet</p>
              )}
              {cat.metrics.map((m, i) => (
                <MetricRow key={i} metric={m} />
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Mission stage status */}
      <div className="rounded-[8px] border border-[#E8EDF3] bg-[#FAFCFB] px-3 py-2">
        <div className="flex items-center gap-2">
          <Wifi size={12} className="text-[#38B88A]" />
          <span className="text-[0.7rem] text-[#6B7280]">
            Stage: <strong className="text-[#374151] capitalize">{missionStage}</strong>
          </span>
          <span className="text-[#9CA3AF] mx-1">·</span>
          <span className="text-[0.7rem] text-[#6B7280]">
            Runtime: <strong className="text-[#374151]">{runtimeStatus}</strong>
          </span>
        </div>
      </div>

      {/* Alert history */}
      {alerts.length > 0 && (
        <div>
          <div className="mb-2 flex items-center gap-1.5">
            <Bell size={12} className="text-[#9CA3AF]" />
            <span className="text-[0.72rem] font-semibold text-[#374151]">Alert History</span>
          </div>
          <div className="max-h-[200px] space-y-1 overflow-y-auto">
            <AnimatePresence>
              {alerts.slice(0, 10).map((alert) => (
                <AlertItem key={alert.id} alert={alert} onDismiss={dismissAlert} />
              ))}
            </AnimatePresence>
          </div>
        </div>
      )}

      {!isObserving && alerts.length === 0 && (
        <div className="rounded-[10px] border border-dashed border-[#D1D9E6] bg-white py-6 text-center">
          <Eye size={18} className="mx-auto mb-1.5 text-[#D1D5DB]" />
          <p className="text-[0.78rem] text-[#9CA3AF]">Observation engine is idle</p>
        </div>
      )}
    </div>
  )
}
