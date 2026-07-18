"use client"

import { useEffect, useState, useMemo } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Activity,
  Building2,
  Users,
  Cpu,
  Plug,
  Brain,
  AlertTriangle,
  Info,
  ShieldCheck,
  HardDrive,
  Wifi,
  Server,
  Clock,
} from "lucide-react"

import { cn } from "@/utils/cn"
import { stagger, variants } from "@/lib/motion-tokens"
import { StatusBadge, KpiCard, DataTable, SectionHeader } from "./shared"
import { fetchDashboardResources } from "@/services/dashboard/resources"
import { fetchDashboardHealth } from "@/services/dashboard/health"
import { runtimeService } from "@/services/runtime"
import { api } from "@/services/api"

// ─── TYPES ─────────────────────────────────────────────────────────────────────

interface AlertItem {
  id: string
  severity: "critical" | "high" | "medium" | "low"
  title: string
  message: string
  time: string
}

interface OpsMission {
  execution_id: string
  objective: string
  status: "running" | "pending" | "completed" | "failed"
  started_at: string
  agent: string
}

interface OpsSnapshot {
  platformHealthy: boolean
  orgCount: number
  userCount: number
  activeWorkers: number
  idleWorkers: number
  activeConnectors: number
  connectorErrors: number
  modelCount: number
}

const SEVERITY_ORDER: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 }

function classifySeverity(status: string): AlertItem["severity"] {
  const s = status.toLowerCase()
  if (s === "failed" || s === "error" || s === "blocked" || s === "rejected" || s === "stopped") return "critical"
  if (s === "warning" || s === "degraded") return "high"
  if (s === "info" || s === "pending") return "medium"
  return "low"
}

function relativeTime(date: Date): string {
  const s = Math.floor((Date.now() - date.getTime()) / 1000)
  if (s < 60) return `${s}s ago`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  const d = Math.floor(h / 24)
  return `${d}d ago`
}

async function fetchOpsSnapshot(): Promise<OpsSnapshot> {
  const results = await Promise.allSettled([
    runtimeService.getAgents(),
    api.get<Record<string, unknown>>("/api/telemetry/runtime"),
    api.get<{ status: string }>("/health"),
    api.get<{ users?: unknown[] }>("/api/auth/me"),
    api.get<{ data?: unknown[] }>("/api/connectors/activity").catch(() => null),
  ])

  const [agentsRes, telemetryRes, healthRes, , connRes] = results

  const agents = agentsRes.status === "fulfilled" ? agentsRes.value.registered_agents : []
  const telemetry = telemetryRes.status === "fulfilled" ? telemetryRes.value as Record<string, unknown> : null
  const health = healthRes.status === "fulfilled" ? healthRes.value : null
  const connectors = connRes && connRes.status === "fulfilled" ? connRes.value : null

  const activeWorkers = telemetry?.active_agents != null ? Number(telemetry.active_agents) : agents.length
  const totalWorkers = agents.length
  const connectorList = (connectors?.data as unknown[] | undefined) ?? []
  const connectorErrors = connectorList.filter((c: unknown) => {
    const entry = c as Record<string, unknown>
    return entry.status === "error" || entry.status === "failed"
  }).length

  return {
    platformHealthy: health?.status === "healthy" || health?.status === "running",
    orgCount: 0,
    userCount: agents.length,
    activeWorkers,
    idleWorkers: Math.max(0, totalWorkers - activeWorkers),
    activeConnectors: connectorList.length - connectorErrors,
    connectorErrors,
    modelCount: 6,
  }
}

function extractMissions(raw: unknown): OpsMission[] {
  const missions: OpsMission[] = []
  if (!raw || typeof raw !== "object") return missions
  const body = raw as Record<string, unknown>

  const active = body["active_missions"]
  if (active && typeof active === "object" && !Array.isArray(active)) {
    for (const [execId, entry] of Object.entries(active)) {
      if (!entry || typeof entry !== "object") continue
      const e = entry as Record<string, unknown>
      const agentsInvolved = e["agentsInvolved"]
      missions.push({
        execution_id: execId,
        objective: typeof e["goal"] === "string" ? e["goal"] : execId,
        status: "running",
        started_at: typeof e["started_at"] === "string" ? e["started_at"] : "",
        agent: Array.isArray(agentsInvolved) && agentsInvolved.length > 0 ? String(agentsInvolved[0]) : "Unknown",
      })
    }
  }

  return missions
}

function extractAlertsFromEvents(raw: unknown): AlertItem[] {
  const alerts: AlertItem[] = []
  if (!raw || typeof raw !== "object") return alerts
  const body = raw as Record<string, unknown>
  const events = body["events"]
  if (!Array.isArray(events)) return alerts

  for (const entry of events.slice(-20)) {
    if (!entry || typeof entry !== "object") continue
    const e = entry as Record<string, unknown>
    const status = String(e["status"] ?? "").toLowerCase()
    const message = String(e["message"] ?? "")
    const eventType = String(e["event_type"] ?? e["type"] ?? "")
    const timestamp = typeof e["timestamp"] === "string" ? new Date(e["timestamp"]) : new Date()

    const severity = classifySeverity(status)
    if (severity === "low" && !message) continue

    alerts.push({
      id: typeof e["event_id"] === "string" ? e["event_id"] : `alert-${alerts.length}`,
      severity,
      title: eventType.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      message: message || `${eventType} event occurred`,
      time: relativeTime(timestamp),
    })
  }

  alerts.sort((a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity])
  return alerts.slice(0, 8)
}

const missionColumns = [
  { label: "Execution ID", key: "execution_id" },
  { label: "Objective", key: "objective" },
  { label: "Status", key: "status", render: (row: OpsMission) => (
    <StatusBadge
      tone={row.status === "running" ? "active" : row.status === "pending" ? "pending" : "error"}
      label={row.status}
    />
  )},
  { label: "Started At", key: "started_at" },
  { label: "Agent", key: "agent" },
]

// ─── COMPONENT ─────────────────────────────────────────────────────────────────

export default function DashboardPanel() {
  const [snapshot, setSnapshot] = useState<OpsSnapshot | null>(null)
  const [alerts, setAlerts] = useState<AlertItem[]>([])
  const [resources, setResources] = useState<{ label: string; used: number; percent: number; color: string }[]>([])
  const [missions, setMissions] = useState<OpsMission[]>([])
  const [selectedMission, setSelectedMission] = useState<OpsMission | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let mounted = true

    async function load() {
      const results = await Promise.allSettled([
        fetchOpsSnapshot(),
        fetchDashboardResources(),
        fetchDashboardHealth(),
        runtimeService.getActiveMissions(),
        runtimeService.getEvents(),
      ])

      if (!mounted) return

      const [snapRes, resRes, , missionsRes, eventsRes] = results

      if (snapRes.status === "fulfilled") setSnapshot(snapRes.value)
      if (resRes.status === "fulfilled") {
        setResources(
          resRes.value.resources.map((r) => ({
            label: r.label,
            used: parseInt(r.value),
            percent: parseInt(r.value),
            color: r.color,
          })),
        )
      }
      if (missionsRes.status === "fulfilled") {
        setMissions(extractMissions(missionsRes.value))
      }
      if (eventsRes.status === "fulfilled") {
        setAlerts(extractAlertsFromEvents(eventsRes.value))
      }

      setLoading(false)
    }

    load()

    const interval = setInterval(load, 30000)
    return () => {
      mounted = false
      clearInterval(interval)
    }
  }, [])

  const isLoading = loading && !snapshot

  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        <KpiCard
          label="Platform Status"
          value={snapshot?.platformHealthy ? "Operational" : "Degraded"}
          icon={Server}
          color={snapshot?.platformHealthy ? "#38B88A" : "#F59E0B"}
        />
        <KpiCard label="Organizations" value={snapshot?.orgCount ?? 0} icon={Building2} color="#6366F1" />
        <KpiCard label="Users" value={snapshot?.userCount ?? 0} icon={Users} trend={{ value: "Active", direction: "up" }} color="#38B88A" />
        <KpiCard
          label="Active Workers"
          value={snapshot?.activeWorkers ?? 0}
          icon={Cpu}
          trend={{ value: `${snapshot?.idleWorkers ?? 0} idle`, direction: (snapshot?.idleWorkers ?? 0) > 0 ? "down" : "up" }}
          color="#F59E0B"
        />
        <KpiCard
          label="Active Connectors"
          value={snapshot?.activeConnectors ?? 0}
          icon={Plug}
          trend={snapshot?.connectorErrors ? { value: `${snapshot.connectorErrors} error`, direction: "down" } : undefined}
          color="#3B82F6"
        />
        <KpiCard label="AI Models" value={snapshot?.modelCount ?? 0} icon={Brain} color="#8B5CF6" />
      </div>

      {/* System Alerts */}
      <div>
        <SectionHeader title="System Alerts" subtitle={isLoading ? "Loading..." : "Recent platform notifications"} />
        <div className="border border-[#E8EDF3] bg-white rounded-[18px] overflow-hidden">
          <div className="divide-y divide-[#E8EDF3]">
            {alerts.length === 0 && !isLoading && (
              <div className="flex flex-col items-center gap-2 py-10 text-center">
                <ShieldCheck className="h-8 w-8 text-[#38B88A]" />
                <p className="text-sm font-medium text-[#111827]">No active alerts</p>
                <p className="text-xs text-[#6B7280]">All systems operating normally</p>
              </div>
            )}
            {isLoading && (
              <div className="flex items-center justify-center py-10">
                <Activity className="h-5 w-5 text-[#9CA3AF] animate-spin" />
              </div>
            )}
            {alerts.map((alert) => {
              const severityColors: Record<string, { dot: string; bg: string; text: string; icon: typeof AlertTriangle }> = {
                critical: { dot: "#EF4444", bg: "bg-[#FEE2E2]", text: "text-[#B91C1C]", icon: AlertTriangle },
                high: { dot: "#F97316", bg: "bg-[#FFEDD5]", text: "text-[#C2410C]", icon: AlertTriangle },
                medium: { dot: "#F59E0B", bg: "bg-[#FEF3C7]", text: "text-[#B45309]", icon: Info },
                low: { dot: "#6B7280", bg: "bg-[#F3F4F6]", text: "text-[#6B7280]", icon: Info },
              }
              const sc = severityColors[alert.severity]
              const Icon = sc.icon
              return (
                <div key={alert.id} className="flex items-center gap-4 px-5 py-3.5 hover:bg-[#F4F7FA] transition-colors duration-100">
                  <div className={cn("p-1.5 rounded-lg shrink-0", sc.bg)}>
                    <Icon className={cn("w-4 h-4", sc.text)} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-[#111827]">{alert.title}</span>
                      <span className={cn("px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider", sc.bg, sc.text)}>
                        {alert.severity}
                      </span>
                    </div>
                    <p className="text-xs text-[#6B7280] mt-0.5 truncate">{alert.message}</p>
                  </div>
                  <span className="text-xs text-[#9CA3AF] shrink-0">{alert.time}</span>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* Resource Utilization */}
      <div>
        <SectionHeader title="Resource Utilization" subtitle="Real-time system resource usage" />
        <div className="border border-[#E8EDF3] bg-white rounded-[18px] p-5 space-y-4">
          {isLoading && (
            <div className="flex items-center justify-center py-6">
              <Activity className="h-5 w-5 text-[#9CA3AF] animate-spin" />
            </div>
          )}
          {!isLoading && resources.length === 0 && (
            <div className="flex flex-col items-center gap-2 py-6 text-center">
              <Activity className="h-8 w-8 text-[#D1D5DB]" />
              <p className="text-sm font-medium text-[#9CA3AF]">No resource data</p>
            </div>
          )}
          {resources.map((r) => (
            <div key={r.label}>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-sm font-medium text-[#111827]">{r.label}</span>
                <span className="text-sm font-semibold text-[#111827]">{r.used}%</span>
              </div>
              <div className="h-2 bg-[#F4F7FA] rounded-full overflow-hidden">
                <motion.div
                  className="h-full rounded-full"
                  style={{ backgroundColor: r.color }}
                  initial={{ width: 0 }}
                  animate={{ width: `${r.percent}%` }}
                  transition={{ duration: 0.8, ease: "easeOut" }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Active Missions */}
      <div>
        <SectionHeader title="Active Missions" subtitle={isLoading ? "Loading..." : "Currently running and pending missions"} />
        <DataTable
          columns={missionColumns}
          data={missions}
          onRowClick={setSelectedMission}
          selectedId={selectedMission?.execution_id}
          idKey="execution_id"
        />
      </div>

      {/* Mission Detail Modal */}
      <AnimatePresence>
        {selectedMission && (
          <motion.div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setSelectedMission(null)}
          >
            <motion.div
              className="bg-white rounded-[18px] shadow-xl w-full max-w-lg p-6"
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              transition={{ duration: 0.2 }}
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-bold text-[#111827]">{selectedMission.execution_id}</h3>
                <StatusBadge
                  tone={selectedMission.status === "running" ? "active" : "pending"}
                  label={selectedMission.status}
                />
              </div>
              <div className="space-y-3 text-sm">
                <div><span className="text-[#6B7280]">Objective:</span> <span className="text-[#111827] font-medium">{selectedMission.objective}</span></div>
                <div><span className="text-[#6B7280]">Agent:</span> <span className="text-[#111827] font-medium">{selectedMission.agent}</span></div>
                <div><span className="text-[#6B7280]">Started:</span> <span className="text-[#111827] font-medium">{selectedMission.started_at}</span></div>
              </div>
              <button
                onClick={() => setSelectedMission(null)}
                className="mt-6 w-full px-4 py-2 rounded-[18px] text-sm font-medium text-[#6B7280] hover:bg-[#F4F7FA] hover:text-[#111827] border border-[#E8EDF3] transition-colors duration-150"
              >
                Close
              </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
