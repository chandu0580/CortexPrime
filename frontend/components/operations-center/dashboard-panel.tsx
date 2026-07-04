"use client"

import { useState } from "react"
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
  Play,
  ChevronRight,
  Server,
  Clock,
} from "lucide-react"

import { cn } from "@/utils/cn"
import { stagger, variants } from "@/lib/motion-tokens"
import { StatusBadge, KpiCard, DataTable, SectionHeader } from "./shared"

// ─── MOCK DATA ─────────────────────────────────────────────────────────────────

interface Alert {
  id: string
  severity: "critical" | "high" | "medium" | "low"
  title: string
  message: string
  time: string
}

interface Resource {
  label: string
  used: number
  total: number
  percent: number
  color: string
}

interface ActiveMission {
  execution_id: string
  objective: string
  status: "running" | "pending" | "completed" | "failed"
  started_at: string
  agent: string
}

const ALERTS: Alert[] = [
  { id: "ALT-001", severity: "critical", title: "Worker Node Failure", message: "Worker node w-1024 unresponsive for 5 minutes", time: "2 min ago" },
  { id: "ALT-002", severity: "high", title: "API Rate Limit Breach", message: "OpenAI rate limit at 92% capacity", time: "15 min ago" },
  { id: "ALT-003", severity: "medium", title: "Connector Sync Delay", message: "GitHub connector sync delayed by 30 minutes", time: "1 hour ago" },
  { id: "ALT-004", severity: "medium", title: "Memory Usage Warning", message: "Neo4j memory usage crossed 75% threshold", time: "2 hours ago" },
  { id: "ALT-005", severity: "low", title: "Certificate Expiry", message: "SSL certificate for api.cortexprime.io expires in 14 days", time: "1 day ago" },
]

const RESOURCES: Resource[] = [
  { label: "CPU", used: 42, total: 100, percent: 42, color: "#38B88A" },
  { label: "Memory", used: 68, total: 100, percent: 68, color: "#F59E0B" },
  { label: "Storage", used: 54, total: 100, percent: 54, color: "#38B88A" },
  { label: "API Rate", used: 23, total: 100, percent: 23, color: "#38B88A" },
]

const ACTIVE_MISSIONS: ActiveMission[] = [
  { execution_id: "EX-2401", objective: "Penetration test - network segment B", status: "running", started_at: "2026-07-04 09:30", agent: "Atlas" },
  { execution_id: "EX-2402", objective: "Vulnerability scan - web assets", status: "running", started_at: "2026-07-04 09:15", agent: "Nexus" },
  { execution_id: "EX-2403", objective: "Phishing simulation campaign", status: "pending", started_at: "2026-07-04 08:00", agent: "Aegis" },
  { execution_id: "EX-2404", objective: "Compliance audit - SOC2 controls", status: "running", started_at: "2026-07-03 14:00", agent: "Oracle" },
]

const SEVERITY_ORDER: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 }

const missionColumns = [
  { label: "Execution ID", key: "execution_id" },
  { label: "Objective", key: "objective" },
  { label: "Status", key: "status", render: (row: ActiveMission) => <StatusBadge tone={row.status === "running" ? "active" : row.status === "pending" ? "pending" : row.status === "completed" ? "active" : "error"} label={row.status} /> },
  { label: "Started At", key: "started_at" },
  { label: "Agent", key: "agent" },
]

// ─── COMPONENT ─────────────────────────────────────────────────────────────────

export default function DashboardPanel() {
  const [selectedMission, setSelectedMission] = useState<ActiveMission | null>(null)

  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        <KpiCard label="Platform Status" value="Operational" icon={Server} color="#38B88A" />
        <KpiCard label="Organizations" value="3" icon={Building2} trend={{ value: "+1 this month", direction: "up" }} color="#6366F1" />
        <KpiCard label="Users" value="48" icon={Users} trend={{ value: "+12%", direction: "up" }} color="#38B88A" />
        <KpiCard label="Active Workers" value="12" icon={Cpu} trend={{ value: "7 idle", direction: "down" }} color="#F59E0B" />
        <KpiCard label="Active Connectors" value="8" icon={Plug} trend={{ value: "1 error", direction: "down" }} color="#3B82F6" />
        <KpiCard label="AI Models" value="6" icon={Brain} color="#8B5CF6" />
      </div>

      {/* System Alerts */}
      <div>
        <SectionHeader title="System Alerts" subtitle="Recent platform notifications" />
        <div className="border border-[#E8EDF3] bg-white rounded-[18px] overflow-hidden">
          <div className="divide-y divide-[#E8EDF3]">
            {ALERTS.sort((a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity]).map((alert) => {
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
          {RESOURCES.map((r) => (
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
        <SectionHeader title="Active Missions" subtitle="Currently running and pending missions" />
        <DataTable
          columns={missionColumns}
          data={ACTIVE_MISSIONS}
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
