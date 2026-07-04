"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import {
  HardDrive,
  Database,
  Server,
  Settings,
  RefreshCw,
  RotateCcw,
  Clock,
  CheckCircle,
  AlertTriangle,
  Play,
  Download,
  Archive,
} from "lucide-react"

import { cn } from "@/utils/cn"
import { StatusBadge, SectionHeader } from "./shared"

// ─── TYPES ─────────────────────────────────────────────────────────────────────

interface ServiceBackup {
  id: string
  service: string
  icon: typeof Database
  color: string
  lastBackup: string
  size: string
  status: "healthy" | "warning" | "error"
}

interface Snapshot {
  id: string
  service: string
  size: string
  created: string
  status: "completed" | "failed" | "in-progress"
}

// ─── MOCK DATA ─────────────────────────────────────────────────────────────────

const SERVICE_BACKUPS: ServiceBackup[] = [
  { id: "SB-001", service: "Redis", icon: Database, color: "#DC382D", lastBackup: "2026-07-04 06:00", size: "1.2 GB", status: "healthy" },
  { id: "SB-002", service: "Neo4j", icon: Server, color: "#008CC1", lastBackup: "2026-07-04 05:00", size: "4.8 GB", status: "healthy" },
  { id: "SB-003", service: "PostgreSQL", icon: HardDrive, color: "#336791", lastBackup: "2026-07-04 04:00", size: "8.3 GB", status: "healthy" },
  { id: "SB-004", service: "Configuration", icon: Settings, color: "#6B7280", lastBackup: "2026-07-04 06:30", size: "240 MB", status: "warning" },
]

const SNAPSHOTS: Snapshot[] = [
  { id: "SN-001", service: "PostgreSQL", size: "8.3 GB", created: "2026-07-04 04:00", status: "completed" },
  { id: "SN-002", service: "Neo4j", size: "4.8 GB", created: "2026-07-04 05:00", status: "completed" },
  { id: "SN-003", service: "Redis", size: "1.2 GB", created: "2026-07-04 06:00", status: "completed" },
  { id: "SN-004", service: "PostgreSQL", size: "8.2 GB", created: "2026-07-03 04:00", status: "completed" },
  { id: "SN-005", service: "Neo4j", size: "4.7 GB", created: "2026-07-03 05:00", status: "failed" },
  { id: "SN-006", service: "Configuration", size: "235 MB", created: "2026-07-04 06:30", status: "completed" },
]

// ─── COMPONENT ─────────────────────────────────────────────────────────────────

export default function BackupPanel() {
  const [selectedTime, setSelectedTime] = useState("2026-07-04T06:00")

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Backup & Restore"
        subtitle="Manage service backups and point-in-time recovery"
        actions={
          <button className="flex items-center gap-2 px-4 py-2 rounded-[18px] bg-[#38B88A] text-white text-sm font-medium hover:bg-[#2F9F77] transition-colors">
            <RefreshCw className="w-4 h-4" />
            Backup All Services
          </button>
        }
      />

      {/* Service Backup Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {SERVICE_BACKUPS.map((svc) => {
          const Icon = svc.icon
          return (
            <div key={svc.id} className="border border-[#E8EDF3] bg-white rounded-[18px] p-5">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ backgroundColor: `${svc.color}15` }}>
                  <Icon className="w-5 h-5" style={{ color: svc.color }} />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-[#111827]">{svc.service}</h3>
                  <StatusBadge tone={svc.status} label={svc.status} />
                </div>
              </div>
              <div className="text-xs space-y-1.5 mb-4">
                <div className="flex justify-between"><span className="text-[#6B7280]">Last Backup</span><span className="text-[#111827] font-medium">{svc.lastBackup}</span></div>
                <div className="flex justify-between"><span className="text-[#6B7280]">Size</span><span className="text-[#111827] font-medium">{svc.size}</span></div>
              </div>
              <button className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-[18px] text-xs font-medium text-[#38B88A] hover:bg-[#E8F5EE] border border-[#38B88A]/30 transition-colors">
                <RefreshCw className="w-3.5 h-3.5" />
                Backup Now
              </button>
            </div>
          )
        })}
      </div>

      {/* Snapshots Table */}
      <div>
        <SectionHeader title="Snapshots" subtitle="Available backup snapshots for restore" />
        <div className="border border-[#E8EDF3] bg-white rounded-[18px] overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#E8EDF3] bg-[#F4F7FA]">
                {["Snapshot ID", "Service", "Size", "Created", "Status", "Action"].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-[#6B7280] uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {SNAPSHOTS.map((snap) => (
                <tr key={snap.id} className="border-b border-[#E8EDF3] hover:bg-[#F4F7FA] transition-colors">
                  <td className="px-4 py-3 font-mono text-xs font-medium text-[#111827]">{snap.id}</td>
                  <td className="px-4 py-3 text-[#111827]">{snap.service}</td>
                  <td className="px-4 py-3 text-[#111827]">{snap.size}</td>
                  <td className="px-4 py-3 text-[#111827]">{snap.created}</td>
                  <td className="px-4 py-3">
                    <StatusBadge
                      tone={snap.status === "completed" ? "active" : snap.status === "failed" ? "error" : "pending"}
                      label={snap.status}
                    />
                  </td>
                  <td className="px-4 py-3">
                    <button
                      disabled={snap.status === "failed"}
                      className={cn(
                        "flex items-center gap-1.5 px-3 py-1.5 rounded-[18px] text-xs font-medium transition-colors",
                        snap.status === "failed"
                          ? "text-[#9CA3AF] cursor-not-allowed"
                          : "text-[#38B88A] hover:bg-[#E8F5EE] border border-[#38B88A]/30",
                      )}
                    >
                      <Download className="w-3.5 h-3.5" />
                      Restore
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Restore Section */}
      <div>
        <SectionHeader title="Point-in-Time Restore" subtitle="Select a timestamp to restore from" />
        <div className="border border-[#E8EDF3] bg-white rounded-[18px] p-5">
          <div className="flex items-end gap-4">
            <div className="flex-1">
              <label className="text-sm font-medium text-[#111827] block mb-1.5">Restore Point</label>
              <input
                type="datetime-local"
                value={selectedTime}
                onChange={(e) => setSelectedTime(e.target.value)}
                className="w-full h-10 px-4 rounded-[18px] bg-[#F4F7FA] border border-[#E8EDF3] text-sm text-[#111827] focus:outline-none focus:ring-2 focus:ring-[#38B88A]/30 focus:border-[#38B88A]"
              />
            </div>
            <div className="flex-1">
              <label className="text-sm font-medium text-[#111827] block mb-1.5">Service</label>
              <select className="w-full h-10 px-4 rounded-[18px] bg-[#F4F7FA] border border-[#E8EDF3] text-sm text-[#111827] focus:outline-none focus:ring-2 focus:ring-[#38B88A]/30 focus:border-[#38B88A]">
                <option>All Services</option>
                <option>PostgreSQL</option>
                <option>Neo4j</option>
                <option>Redis</option>
                <option>Configuration</option>
              </select>
            </div>
            <button className="flex items-center gap-2 px-5 py-2 rounded-[18px] bg-[#38B88A] text-white text-sm font-medium hover:bg-[#2F9F77] transition-colors">
              <RotateCcw className="w-4 h-4" />
              Restore
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}