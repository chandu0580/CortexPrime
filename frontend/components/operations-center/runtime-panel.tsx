"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import {
  Terminal,
  Activity,
  Cpu,
  HardDrive,
  Wifi,
  Server,
  Play,
  Pause,
  Clock,
  List,
} from "lucide-react"

import { cn } from "@/utils/cn"
import { StatusBadge, KpiCard, SectionHeader } from "./shared"

// ─── TYPES ─────────────────────────────────────────────────────────────────────

interface QueueCard {
  id: string
  label: string
  items: { label: string; value: number; color: string }[]
  icon: typeof List
  color: string
}

interface ResourceUsage {
  label: string
  used: number
  total: number
  percent: number
  color: string
}

interface ActiveExecution {
  id: string
  objective: string
  agent: string
  stage: string
  duration: string
  status: "running" | "pending" | "completed" | "failed"
}

// ─── MOCK DATA ─────────────────────────────────────────────────────────────────

const QUEUE_CARDS: QueueCard[] = [
  {
    id: "mission", label: "Mission Queue", icon: Activity, color: "#38B88A",
    items: [
      { label: "Pending", value: 12, color: "#F59E0B" },
      { label: "Processing", value: 3, color: "#38B88A" },
    ],
  },
  {
    id: "retry", label: "Retry Queue", icon: Terminal, color: "#F59E0B",
    items: [{ label: "Pending", value: 5, color: "#F59E0B" }],
  },
  {
    id: "worker", label: "Worker Queue", icon: Server, color: "#3B82F6",
    items: [{ label: "Pending", value: 8, color: "#3B82F6" }],
  },
  {
    id: "execution", label: "Execution Queue", icon: Play, color: "#8B5CF6",
    items: [{ label: "Pending", value: 2, color: "#8B5CF6" }],
  },
]

const RESOURCES: ResourceUsage[] = [
  { label: "CPU", used: 52, total: 100, percent: 52, color: "#38B88A" },
  { label: "Memory", used: 71, total: 100, percent: 71, color: "#F59E0B" },
  { label: "Disk", used: 44, total: 100, percent: 44, color: "#38B88A" },
  { label: "Network", used: 33, total: 100, percent: 33, color: "#3B82F6" },
]

const EXECUTIONS: ActiveExecution[] = [
  { id: "EX-2405", objective: "Network reconnaissance - DMZ", agent: "Atlas", stage: "Scanning", duration: "4m 32s", status: "running" },
  { id: "EX-2406", objective: "Log analysis - SIEM correlation", agent: "Nexus", stage: "Analysis", duration: "12m 15s", status: "running" },
  { id: "EX-2407", objective: "Vulnerability validation - CVE-2026-1234", agent: "Aegis", stage: "Exploitation", duration: "2m 48s", status: "running" },
  { id: "EX-2408", objective: "Compliance check - PCI DSS 4.0", agent: "Oracle", stage: "Reporting", duration: "8m 05s", status: "running" },
  { id: "EX-2409", objective: "Asset discovery - cloud inventory", agent: "Atlas", stage: "Discovery", duration: "1m 20s", status: "pending" },
  { id: "EX-2410", objective: "Threat hunting - IOCs", agent: "Nexus", stage: "Correlation", duration: "0m 00s", status: "pending" },
]

const execColumns = [
  { label: "ID", key: "id" },
  { label: "Objective", key: "objective" },
  { label: "Agent", key: "agent" },
  { label: "Stage", key: "stage" },
  { label: "Duration", key: "duration" },
  {
    label: "Status",
    key: "status",
    render: (row: ActiveExecution) => (
      <StatusBadge
        tone={row.status === "running" ? "active" : row.status === "pending" ? "pending" : row.status === "completed" ? "healthy" : "error"}
        label={row.status}
      />
    ),
  },
]

// ─── COMPONENT ─────────────────────────────────────────────────────────────────

export default function RuntimePanel() {
  return (
    <div className="space-y-6">
      <SectionHeader title="Runtime" subtitle="Queue management and active execution monitoring" />

      {/* Queue Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {QUEUE_CARDS.map((queue) => {
          const Icon = queue.icon
          const total = queue.items.reduce((sum, i) => sum + i.value, 0)
          return (
            <div key={queue.id} className="border border-[#E8EDF3] bg-white rounded-[18px] p-5">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ backgroundColor: `${queue.color}15` }}>
                  <Icon className="w-5 h-5" style={{ color: queue.color }} />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-[#111827]">{queue.label}</h3>
                  <p className="text-2xl font-bold" style={{ color: queue.color }}>{total}</p>
                </div>
              </div>
              <div className="space-y-2">
                {queue.items.map((item) => (
                  <div key={item.label} className="flex items-center justify-between text-xs">
                    <span className="text-[#6B7280]">{item.label}</span>
                    <span className="font-semibold" style={{ color: item.color }}>{item.value}</span>
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </div>

      {/* Resource Usage */}
      <div>
        <SectionHeader title="Resource Usage" subtitle="Runtime system utilization" />
        <div className="border border-[#E8EDF3] bg-white rounded-[18px] p-5 space-y-4">
          {RESOURCES.map((r) => (
            <div key={r.label}>
              <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-2">
                  {r.label === "CPU" && <Cpu className="w-3.5 h-3.5 text-[#6B7280]" />}
                  {r.label === "Memory" && <HardDrive className="w-3.5 h-3.5 text-[#6B7280]" />}
                  {r.label === "Disk" && <HardDrive className="w-3.5 h-3.5 text-[#6B7280]" />}
                  {r.label === "Network" && <Wifi className="w-3.5 h-3.5 text-[#6B7280]" />}
                  <span className="text-sm font-medium text-[#111827]">{r.label}</span>
                </div>
                <span className="text-sm font-semibold text-[#111827]">{r.used}%</span>
              </div>
              <div className="h-2.5 bg-[#F4F7FA] rounded-full overflow-hidden">
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

      {/* Active Executions */}
      <div>
        <SectionHeader title="Active Executions" subtitle="Currently running and queued missions" />
        <div className="border border-[#E8EDF3] bg-white rounded-[18px] overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#E8EDF3] bg-[#F4F7FA]">
                {execColumns.map((col) => (
                  <th key={col.key} className="px-4 py-3 text-left text-xs font-semibold text-[#6B7280] uppercase tracking-wider">{col.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {EXECUTIONS.map((ex) => (
                <tr key={ex.id} className="border-b border-[#E8EDF3] hover:bg-[#F4F7FA] transition-colors duration-100">
                  {execColumns.map((col) => (
                    <td key={col.key} className="px-4 py-3 text-[#111827] whitespace-nowrap">
                      {col.render ? col.render(ex) : (ex as any)[col.key] ?? "-"}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}