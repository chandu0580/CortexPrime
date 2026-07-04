"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import {
  FileKey,
  Copy,
  Check,
  Users,
  Activity,
  HardDrive,
  BarChart3,
  Calendar,
  CheckCircle,
} from "lucide-react"

import { cn } from "@/utils/cn"
import { StatusBadge, SectionHeader } from "./shared"

// ─── TYPES ─────────────────────────────────────────────────────────────────────

interface LicenseInfo {
  type: string
  status: "Active" | "Expired" | "Grace"
  seatsUsed: number
  seatsTotal: number
  expiry: string
}

interface ConsumptionChart {
  label: string
  value: number
  max: number
  color: string
  icon: typeof Activity
}

interface MonthlyConsumption {
  month: string
  missions: number
  activeUsers: number
  storageGB: number
  apiCalls: number
}

// ─── MOCK DATA ─────────────────────────────────────────────────────────────────

const LICENSE_INFO: LicenseInfo = {
  type: "Enterprise",
  status: "Active",
  seatsUsed: 50,
  seatsTotal: 250,
  expiry: "Dec 31, 2026",
}

const CONSUMPTION: ConsumptionChart[] = [
  { label: "Missions Executed", value: 1247, max: 5000, color: "#38B88A", icon: Activity },
  { label: "Active Users", value: 50, max: 250, color: "#3B82F6", icon: Users },
  { label: "Storage Consumed", value: 245, max: 1000, color: "#F59E0B", icon: HardDrive },
  { label: "API Calls", value: 89200, max: 500000, color: "#8B5CF6", icon: BarChart3 },
]

const MONTHLY: MonthlyConsumption[] = [
  { month: "Feb", missions: 180, activeUsers: 38, storageGB: 210, apiCalls: 62000 },
  { month: "Mar", missions: 220, activeUsers: 42, storageGB: 220, apiCalls: 71000 },
  { month: "Apr", missions: 195, activeUsers: 44, storageGB: 228, apiCalls: 75000 },
  { month: "May", missions: 260, activeUsers: 47, storageGB: 235, apiCalls: 81000 },
  { month: "Jun", missions: 290, activeUsers: 48, storageGB: 242, apiCalls: 85000 },
  { month: "Jul", missions: 315, activeUsers: 50, storageGB: 245, apiCalls: 89200 },
]

const LICENSE_KEY = "CRPRM-ENT-3A8F-2C9B-7D4E-1F6H"

// ─── COMPONENT ─────────────────────────────────────────────────────────────────

export default function LicensingPanel() {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(LICENSE_KEY)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="space-y-6">
      <SectionHeader title="Licensing" subtitle="License information and usage metrics" />

      {/* License Info Card */}
      <div className="border border-[#E8EDF3] bg-white rounded-[18px] p-6">
        <div className="flex items-start justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-[#E8F5EE] flex items-center justify-center">
              <FileKey className="w-6 h-6 text-[#38B88A]" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-[#111827]">{LICENSE_INFO.type} License</h3>
              <div className="flex items-center gap-2 mt-0.5">
                <StatusBadge tone="active" label={LICENSE_INFO.status} />
              </div>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-6">
          <div>
            <p className="text-xs text-[#6B7280] font-medium uppercase tracking-wider mb-1">Seats</p>
            <p className="text-xl font-bold text-[#111827]">{LICENSE_INFO.seatsUsed} / {LICENSE_INFO.seatsTotal}</p>
            <div className="h-2 bg-[#F4F7FA] rounded-full mt-2 overflow-hidden">
              <motion.div
                className="h-full rounded-full bg-[#38B88A]"
                initial={{ width: 0 }}
                animate={{ width: `${(LICENSE_INFO.seatsUsed / LICENSE_INFO.seatsTotal) * 100}%` }}
                transition={{ duration: 0.8 }}
              />
            </div>
          </div>
          <div>
            <p className="text-xs text-[#6B7280] font-medium uppercase tracking-wider mb-1">Expiry</p>
            <div className="flex items-center gap-2">
              <Calendar className="w-5 h-5 text-[#6B7280]" />
              <p className="text-xl font-bold text-[#111827]">{LICENSE_INFO.expiry}</p>
            </div>
          </div>
          <div>
            <p className="text-xs text-[#6B7280] font-medium uppercase tracking-wider mb-1">License Key</p>
            <div className="flex items-center gap-2">
              <code className="text-xs font-mono bg-[#F4F7FA] px-3 py-2 rounded-xl text-[#111827] flex-1 truncate">{LICENSE_KEY}</code>
              <button
                onClick={handleCopy}
                className="p-2 rounded-xl text-[#6B7280] hover:bg-[#F4F7FA] hover:text-[#38B88A] transition-colors"
              >
                {copied ? <Check className="w-4 h-4 text-[#38B88A]" /> : <Copy className="w-4 h-4" />}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Usage Charts */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {CONSUMPTION.map((item) => {
          const Icon = item.icon
          return (
            <div key={item.label} className="border border-[#E8EDF3] bg-white rounded-[18px] p-5">
              <div className="flex items-center gap-2 mb-3">
                <Icon className="w-4 h-4" style={{ color: item.color }} />
                <span className="text-xs font-medium text-[#6B7280]">{item.label}</span>
              </div>
              <p className="text-xl font-bold text-[#111827]">{item.value.toLocaleString()}</p>
              <div className="h-2 bg-[#F4F7FA] rounded-full mt-2 overflow-hidden">
                <motion.div
                  className="h-full rounded-full"
                  style={{ backgroundColor: item.color }}
                  initial={{ width: 0 }}
                  animate={{ width: `${(item.value / item.max) * 100}%` }}
                  transition={{ duration: 0.8 }}
                />
              </div>
              <p className="text-xs text-[#6B7280] mt-1">of {item.max.toLocaleString()}</p>
            </div>
          )
        })}
      </div>

      {/* Monthly Consumption Table */}
      <div>
        <SectionHeader title="Monthly Consumption" subtitle="Usage breakdown by month" />
        <div className="border border-[#E8EDF3] bg-white rounded-[18px] overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#E8EDF3] bg-[#F4F7FA]">
                {["Month", "Missions", "Active Users", "Storage (GB)", "API Calls"].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-[#6B7280] uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {MONTHLY.map((row) => (
                <tr key={row.month} className="border-b border-[#E8EDF3] hover:bg-[#F4F7FA] transition-colors">
                  <td className="px-4 py-3 font-medium text-[#111827]">{row.month}</td>
                  <td className="px-4 py-3 text-[#111827]">{row.missions}</td>
                  <td className="px-4 py-3 text-[#111827]">{row.activeUsers}</td>
                  <td className="px-4 py-3 text-[#111827]">{row.storageGB}</td>
                  <td className="px-4 py-3 text-[#111827]">{row.apiCalls.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}