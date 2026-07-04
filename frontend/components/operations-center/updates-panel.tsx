"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import {
  RefreshCw,
  Download,
  Upload,
  RotateCcw,
  ArrowUpCircle,
  CheckCircle,
  Clock,
  AlertTriangle,
  FileText,
  Server,
  Cpu,
  HardDrive,
  Database,
} from "lucide-react"

import { cn } from "@/utils/cn"
import { StatusBadge, SectionHeader } from "./shared"

// ─── TYPES ─────────────────────────────────────────────────────────────────────

interface AvailableUpdate {
  id: string
  version: string
  releaseDate: string
  size: string
  status: "Available" | "Installed"
  changelog: string
}

interface RollbackPoint {
  id: string
  version: string
  date: string
}

interface CompatibilityItem {
  component: string
  current: string
  target: string
  compatible: "Yes" | "No"
}

// ─── MOCK DATA ─────────────────────────────────────────────────────────────────

const CURRENT_VERSION = "v3.2.1"

const AVAILABLE_UPDATES: AvailableUpdate[] = [
  { id: "UP-001", version: "v3.3.0", releaseDate: "2026-07-01", size: "48 MB", status: "Available", changelog: "New connector framework, improved worker orchestration" },
  { id: "UP-002", version: "v3.2.2", releaseDate: "2026-06-15", size: "12 MB", status: "Available", changelog: "Bug fixes for runtime scheduler, security patches" },
  { id: "UP-003", version: "v3.2.1", releaseDate: "2026-06-01", size: "24 MB", status: "Installed", changelog: "Performance improvements, audit log enhancements" },
  { id: "UP-004", version: "v3.2.0", releaseDate: "2026-05-15", size: "36 MB", status: "Installed", changelog: "Multi-tenant support, RBAC overhaul" },
]

const ROLLBACK_POINTS: RollbackPoint[] = [
  { id: "RB-001", version: "v3.2.0", date: "2026-06-01 14:30" },
  { id: "RB-002", version: "v3.1.5", date: "2026-05-15 09:00" },
  { id: "RB-003", version: "v3.1.0", date: "2026-04-20 11:45" },
]

const COMPATIBILITY: CompatibilityItem[] = [
  { component: "Runtime Engine", current: "v3.2.1", target: "v3.3.0", compatible: "Yes" },
  { component: "Worker Service", current: "v3.2.0", target: "v3.3.0", compatible: "Yes" },
  { component: "Webhook Gateway", current: "v3.1.0", target: "v3.3.0", compatible: "No" },
  { component: "Analytics Pipeline", current: "v3.2.1", target: "v3.3.0", compatible: "Yes" },
  { component: "Connector Manager", current: "v3.0.5", target: "v3.3.0", compatible: "No" },
]

// ─── COMPONENT ─────────────────────────────────────────────────────────────────

export default function UpdatesPanel() {
  const [showChangelog, setShowChangelog] = useState<string | null>(null)
  const [checking, setChecking] = useState(false)

  const handleCheck = () => {
    setChecking(true)
    setTimeout(() => setChecking(false), 1500)
  }

  return (
    <div className="space-y-6">
      <SectionHeader title="Platform Updates" subtitle="Manage software versions and rollbacks" />

      {/* Current Version */}
      <div className="border border-[#E8EDF3] bg-white rounded-[18px] p-5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#E8F5EE] flex items-center justify-center">
            <RefreshCw className="w-5 h-5 text-[#38B88A]" />
          </div>
          <div>
            <p className="text-xs text-[#6B7280] font-medium">Current Version</p>
            <p className="text-lg font-bold text-[#111827]">{CURRENT_VERSION}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleCheck}
            disabled={checking}
            className="flex items-center gap-2 px-4 py-2 rounded-[18px] text-sm font-medium text-[#6B7280] hover:bg-[#F4F7FA] hover:text-[#111827] border border-[#E8EDF3] transition-colors"
          >
            <RefreshCw className={cn("w-4 h-4", checking && "animate-spin")} />
            Check for Updates
          </button>
          <button className="flex items-center gap-2 px-4 py-2 rounded-[18px] bg-[#38B88A] text-white text-sm font-medium hover:bg-[#2F9F77] transition-colors">
            <ArrowUpCircle className="w-4 h-4" />
            Update All
          </button>
        </div>
      </div>

      {/* Available Updates */}
      <div>
        <SectionHeader title="Available Updates" />
        <div className="border border-[#E8EDF3] bg-white rounded-[18px] overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#E8EDF3] bg-[#F4F7FA]">
                {["Version", "Release Date", "Size", "Status", "Changelog"].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-[#6B7280] uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {AVAILABLE_UPDATES.map((upd) => (
                <tr key={upd.id} className="border-b border-[#E8EDF3] hover:bg-[#F4F7FA] transition-colors">
                  <td className="px-4 py-3 font-mono font-bold text-[#111827]">{upd.version}</td>
                  <td className="px-4 py-3 text-[#111827]">{upd.releaseDate}</td>
                  <td className="px-4 py-3 text-[#111827]">{upd.size}</td>
                  <td className="px-4 py-3">
                    <StatusBadge tone={upd.status === "Installed" ? "active" : "warning"} label={upd.status} />
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => setShowChangelog(showChangelog === upd.id ? null : upd.id)}
                      className="flex items-center gap-1.5 text-xs font-medium text-[#38B88A] hover:text-[#2F9F77] transition-colors"
                    >
                      <FileText className="w-3.5 h-3.5" />
                      {showChangelog === upd.id ? "Hide" : "View"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {showChangelog && (
          <div className="mt-2 px-4 py-3 bg-[#F4F7FA] border border-[#E8EDF3] rounded-[18px]">
            <p className="text-sm text-[#111827]">{AVAILABLE_UPDATES.find((u) => u.id === showChangelog)?.changelog}</p>
          </div>
        )}
      </div>

      {/* Rollback Section */}
      <div>
        <SectionHeader title="Rollback Points" subtitle="Last 3 available rollback snapshots" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {ROLLBACK_POINTS.map((rb) => (
            <div key={rb.id} className="border border-[#E8EDF3] bg-white rounded-[18px] p-4">
              <div className="flex items-center gap-2 mb-2">
                <RotateCcw className="w-4 h-4 text-[#F59E0B]" />
                <span className="font-mono font-bold text-[#111827]">{rb.version}</span>
              </div>
              <p className="text-xs text-[#6B7280] mb-3">{rb.date}</p>
              <button className="w-full px-3 py-1.5 rounded-[18px] text-xs font-medium text-[#6B7280] hover:bg-[#F4F7FA] hover:text-[#111827] border border-[#E8EDF3] transition-colors">
                Rollback to {rb.version}
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Compatibility Matrix */}
      <div>
        <SectionHeader title="Compatibility Matrix" subtitle="Component compatibility with target version v3.3.0" />
        <div className="border border-[#E8EDF3] bg-white rounded-[18px] overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#E8EDF3] bg-[#F4F7FA]">
                {["Component", "Current", "Target", "Compatible"].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-[#6B7280] uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {COMPATIBILITY.map((item, i) => (
                <tr key={i} className="border-b border-[#E8EDF3] hover:bg-[#F4F7FA] transition-colors">
                  <td className="px-4 py-3 font-medium text-[#111827]">{item.component}</td>
                  <td className="px-4 py-3 font-mono text-[#111827]">{item.current}</td>
                  <td className="px-4 py-3 font-mono text-[#111827]">{item.target}</td>
                  <td className="px-4 py-3">
                    {item.compatible === "Yes" ? (
                      <span className="inline-flex items-center gap-1 text-xs font-medium text-[#38B88A]"><CheckCircle className="w-3.5 h-3.5" /> Yes</span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-xs font-medium text-[#EF4444]"><AlertTriangle className="w-3.5 h-3.5" /> No</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}