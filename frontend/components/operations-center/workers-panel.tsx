"use client"

import { useState } from "react"
import {
  Monitor,
  Headphones,
  MonitorSmartphone,
  Cpu,
  Activity,
  RotateCcw,
  XCircle,
  Clock,
  HardDrive,
  Gauge,
} from "lucide-react"

import { cn } from "@/utils/cn"
import { StatusBadge, KpiCard, SectionHeader } from "./shared"

// ─── TYPES ─────────────────────────────────────────────────────────────────────

interface WorkerCategory {
  id: string
  label: string
  icon: typeof Monitor
  color: string
  active: number
  idle: number
}

interface Worker {
  id: string
  type: "Browser" | "Voice" | "Desktop"
  status: "active" | "idle" | "error"
  uptime: string
  actionsPerSec: number
  memory: string
}

// ─── MOCK DATA ─────────────────────────────────────────────────────────────────

const WORKER_CATEGORIES: WorkerCategory[] = [
  { id: "browser", label: "Browser", icon: Monitor, color: "#3B82F6", active: 4, idle: 2 },
  { id: "voice", label: "Voice", icon: Headphones, color: "#8B5CF6", active: 2, idle: 1 },
  { id: "desktop", label: "Desktop", icon: MonitorSmartphone, color: "#38B88A", active: 1, idle: 0 },
]

const WORKERS: Worker[] = [
  { id: "w-1001", type: "Browser", status: "active", uptime: "12h 34m", actionsPerSec: 24, memory: "256MB" },
  { id: "w-1002", type: "Browser", status: "active", uptime: "8h 12m", actionsPerSec: 18, memory: "192MB" },
  { id: "w-1003", type: "Browser", status: "active", uptime: "6h 45m", actionsPerSec: 31, memory: "320MB" },
  { id: "w-1004", type: "Browser", status: "idle", uptime: "4h 20m", actionsPerSec: 0, memory: "128MB" },
  { id: "w-1005", type: "Browser", status: "active", uptime: "24h 00m", actionsPerSec: 15, memory: "512MB" },
  { id: "w-1006", type: "Browser", status: "idle", uptime: "1h 05m", actionsPerSec: 0, memory: "64MB" },
  { id: "w-2001", type: "Voice", status: "active", uptime: "48h 12m", actionsPerSec: 8, memory: "512MB" },
  { id: "w-2002", type: "Voice", status: "active", uptime: "36h 30m", actionsPerSec: 12, memory: "768MB" },
  { id: "w-2003", type: "Voice", status: "idle", uptime: "2h 15m", actionsPerSec: 0, memory: "256MB" },
  { id: "w-3001", type: "Desktop", status: "active", uptime: "72h 00m", actionsPerSec: 6, memory: "1.2GB" },
]

// ─── COMPONENT ─────────────────────────────────────────────────────────────────

export default function WorkersPanel() {
  const [workers, setWorkers] = useState(WORKERS)
  const [filter, setFilter] = useState<string>("All")

  const restartWorker = (id: string) => {
    setWorkers((prev) => prev.map((w) => (w.id === id ? { ...w, status: "idle", uptime: "0m", actionsPerSec: 0 } : w)))
  }

  const drainWorker = (id: string) => {
    setWorkers((prev) => prev.map((w) => (w.id === id ? { ...w, status: "idle" } : w)))
  }

  const filteredWorkers = filter === "All" ? workers : workers.filter((w) => w.type === filter)

  return (
    <div className="space-y-6">
      <SectionHeader title="Workers" subtitle="Monitor and manage worker instances" />

      {/* Category Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {WORKER_CATEGORIES.map((cat) => {
          const Icon = cat.icon
          const total = cat.active + cat.idle
          return (
            <div key={cat.id} className="border border-[#E8EDF3] bg-white rounded-[18px] p-5">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ backgroundColor: `${cat.color}15` }}>
                  <Icon className="w-5 h-5" style={{ color: cat.color }} />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-[#111827]">{cat.label}</h3>
                  <p className="text-xs text-[#6B7280]">{total} total workers</p>
                </div>
              </div>
              <div className="flex gap-4">
                <div className="flex-1 text-center p-3 rounded-xl bg-[#E8F5EE]">
                  <p className="text-xl font-bold text-[#38B88A]">{cat.active}</p>
                  <p className="text-xs text-[#2F9F77] font-medium">Active</p>
                </div>
                <div className="flex-1 text-center p-3 rounded-xl bg-[#F3F4F6]">
                  <p className="text-xl font-bold text-[#6B7280]">{cat.idle}</p>
                  <p className="text-xs text-[#6B7280] font-medium">Idle</p>
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {/* Health Overview Chips */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold text-[#6B7280] uppercase tracking-wider">Health:</span>
        {["All", "Browser", "Voice", "Desktop"].map((t) => (
          <button
            key={t}
            onClick={() => setFilter(t)}
            className={cn(
              "px-3 py-1.5 rounded-[18px] text-xs font-medium transition-colors duration-150",
              filter === t
                ? "bg-[#38B88A] text-white"
                : "bg-white border border-[#E8EDF3] text-[#6B7280] hover:text-[#111827] hover:bg-[#F4F7FA]",
            )}
          >
            {t}
          </button>
        ))}
        <span className="w-1 h-1 rounded-full bg-[#D1D5DB]" />
        <StatusBadge tone="active" label="7 Active" />
        <StatusBadge tone="inactive" label="3 Idle" />
      </div>

      {/* Worker Table */}
      <div className="border border-[#E8EDF3] bg-white rounded-[18px] overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#E8EDF3] bg-[#F4F7FA]">
              {["Worker ID", "Type", "Status", "Uptime", "Actions/sec", "Memory", "Actions"].map((h) => (
                <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-[#6B7280] uppercase tracking-wider">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filteredWorkers.map((worker) => (
              <tr key={worker.id} className="border-b border-[#E8EDF3] hover:bg-[#F4F7FA] transition-colors duration-100">
                <td className="px-4 py-3 font-mono text-xs font-medium text-[#111827]">{worker.id}</td>
                <td className="px-4 py-3">
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-[#F4F7FA] text-[#6B7280]">
                    <Cpu className="w-3 h-3" />
                    {worker.type}
                  </span>
                </td>
                <td className="px-4 py-3"><StatusBadge tone={worker.status === "active" ? "active" : worker.status === "idle" ? "inactive" : "error"} label={worker.status} /></td>
                <td className="px-4 py-3 text-[#111827]">{worker.uptime}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="h-1.5 w-16 bg-[#F4F7FA] rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full bg-[#38B88A] transition-all duration-300"
                        style={{ width: `${Math.min(100, (worker.actionsPerSec / 40) * 100)}%` }}
                      />
                    </div>
                    <span className="text-xs font-medium text-[#111827]">{worker.actionsPerSec}</span>
                  </div>
                </td>
                <td className="px-4 py-3 text-[#111827]">{worker.memory}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => restartWorker(worker.id)}
                      className="p-1.5 rounded-lg text-[#6B7280] hover:bg-[#F4F7FA] hover:text-[#F59E0B] transition-colors duration-150"
                      title="Restart"
                    >
                      <RotateCcw className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => drainWorker(worker.id)}
                      className="p-1.5 rounded-lg text-[#6B7280] hover:bg-[#F4F7FA] hover:text-[#EF4444] transition-colors duration-150"
                      title="Drain"
                    >
                      <XCircle className="w-4 h-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}