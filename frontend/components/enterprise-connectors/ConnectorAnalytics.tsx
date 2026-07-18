"use client"

import { motion } from "framer-motion"
import {
  Activity, Clock, CheckCircle, XCircle, Zap, BarChart3,
  TrendingUp, TrendingDown, Wifi, Shield,
} from "lucide-react"
import { dur, ease } from "@/lib/motion-tokens"
import type { Connector } from "./types"

interface ConnectorAnalyticsProps {
  connector: Connector
}

function MetricCard({
  icon, label, value, sublabel, trend, trendUp, color,
}: {
  icon: React.ReactNode
  label: string
  value: string
  sublabel?: string
  trend?: string
  trendUp?: boolean
  color: string
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: dur.base, ease: ease.out }}
      className="rounded-[12px] border border-[#E8EDF3] bg-white p-4 shadow-sm"
    >
      <div className="flex items-center gap-2 mb-2">
        <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${color} bg-opacity-10`}>
          {icon}
        </div>
      </div>
      <p className="text-[1.2rem] font-extrabold text-[#111827] tracking-tight">{value}</p>
      <p className="text-[0.72rem] text-[#6B7280] font-medium">{label}</p>
      {sublabel && <p className="text-[0.65rem] text-[#9CA3AF] mt-0.5">{sublabel}</p>}
      {trend && (
        <div className="flex items-center gap-1 mt-1">
          {trendUp ? (
            <TrendingUp size={12} className="text-[#38B88A]" />
          ) : (
            <TrendingDown size={12} className="text-[#EF4444]" />
          )}
          <span className={`text-[0.65rem] font-bold ${trendUp ? 'text-[#38B88A]' : 'text-[#EF4444]'}`}>
            {trend}
          </span>
        </div>
      )}
    </motion.div>
  )
}

function LatencyBar({ latencyMs, maxLatency = 1000 }: { latencyMs: number | null; maxLatency?: number }) {
  if (latencyMs == null) return <span className="text-[0.72rem] text-[#9CA3AF]">--</span>

  const pct = Math.min((latencyMs / maxLatency) * 100, 100)
  const color = latencyMs < 200 ? "bg-[#38B88A]"
    : latencyMs < 500 ? "bg-amber-400"
    : "bg-red-400"

  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 rounded-full bg-gray-100 overflow-hidden">
        <div
          className={`h-full rounded-full ${color} transition-all duration-500`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-[0.72rem] font-semibold text-[#374151] w-16 text-right">
        {latencyMs}ms
      </span>
    </div>
  )
}

function SuccessRateRing({ rate }: { rate: number }) {
  const size = 80
  const r = 30
  const circ = 2 * Math.PI * r
  const dash = circ * (rate / 100)
  const color = rate >= 95 ? "#38B88A" : rate >= 80 ? "#F59E0B" : "#EF4444"

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#F3F4F6" strokeWidth="8" />
        <circle
          cx={size / 2} cy={size / 2} r={r} fill="none"
          stroke={color} strokeWidth="8"
          strokeDasharray={`${dash} ${circ - dash}`}
          strokeLinecap="round"
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ transition: "stroke-dasharray 0.5s ease" }}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-[1rem] font-extrabold text-[#111827]" style={{ color }}>{rate}%</span>
      </div>
    </div>
  )
}

function ActivitySparkline() {
  const points = [3, 7, 4, 9, 6, 12, 8, 15, 10, 18, 14, 20, 16, 22, 18, 15, 12, 18, 14, 10]
  const max = Math.max(...points)
  const width = 120
  const height = 32
  const stepX = width / (points.length - 1)

  const pathD = points.map((p, i) => {
    const x = i * stepX
    const y = height - (p / max) * height
    return `${i === 0 ? 'M' : 'L'} ${x} ${y}`
  }).join(' ')

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="overflow-visible">
      <defs>
        <linearGradient id="sparkGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#38B88A" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#38B88A" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={`${pathD} L ${width} ${height} L 0 ${height} Z`} fill="url(#sparkGrad)" />
      <path d={pathD} fill="none" stroke="#38B88A" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export default function ConnectorAnalytics({ connector }: ConnectorAnalyticsProps) {
  const isConnected = connector.status === "connected" || connector.status === "healthy"
  const latencyMs = connector.latencyMs ?? null

  const metrics = [
    { icon: <Wifi size={14} className="text-[#38B88A]" />, label: "Success Rate", value: isConnected ? "98.5%" : "--", sublabel: "Last 24 hours", trend: "+0.5%", trendUp: true, color: "bg-[#ECFBF4]" },
    { icon: <Zap size={14} className="text-amber-500" />, label: "Avg. Latency", value: latencyMs ? `${latencyMs}ms` : "--", sublabel: "Last 100 requests", trend: latencyMs && latencyMs < 200 ? "-12ms" : undefined, trendUp: latencyMs ? latencyMs < 200 : undefined, color: "bg-amber-50" },
    { icon: <Activity size={14} className="text-blue-500" />, label: "Total Operations", value: isConnected ? "1,847" : "--", sublabel: "Today", trend: "+12.3%", trendUp: true, color: "bg-blue-50" },
    { icon: <Clock size={14} className="text-purple-500" />, label: "Last Sync", value: connector.lastSync || "--", sublabel: isConnected ? "Auto-sync enabled" : "Not syncing", color: "bg-purple-50" },
  ]

  const recentOperations = [
    { op: "List Repositories", status: "success", time: "2m ago", duration: "183ms" },
    { op: "Create Issue", status: "success", time: "5m ago", duration: "245ms" },
    { op: "Sync Webhook", status: "success", time: "8m ago", duration: "412ms" },
    { op: "Update PR Status", status: "error", time: "12m ago", duration: "0ms" },
    { op: "Fetch Commits", status: "success", time: "15m ago", duration: "167ms" },
  ]

  return (
    <div className="flex flex-col gap-5">
      {/* Header */}
      <div className="flex items-center gap-3 pb-4 border-b border-[#E8EDF3]">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#ECFBF4] text-[#38B88A]">
          <BarChart3 size={16} />
        </div>
        <div>
          <p className="text-[0.82rem] font-bold text-[#111827]">Connector Analytics</p>
          <p className="text-[0.7rem] text-[#6B7280]">Performance metrics and activity overview</p>
        </div>
      </div>

      {/* Metrics grid */}
      <div className="grid grid-cols-2 gap-3">
        {metrics.map((m) => (
          <MetricCard key={m.label} {...m} />
        ))}
      </div>

      {/* Success rate + Latency */}
      <div className="grid grid-cols-2 gap-4">
        <div className="rounded-[12px] border border-[#E8EDF3] bg-white p-4 shadow-sm">
          <p className="text-[0.72rem] font-bold text-[#6B7280] mb-3 uppercase tracking-wider">Success Rate</p>
          <div className="flex items-center gap-4">
            <SuccessRateRing rate={isConnected ? 98 : 0} />
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-[0.7rem]">
                <CheckCircle size={10} className="text-[#38B88A]" />
                <span className="text-[#374151]">1,812 successful</span>
              </div>
              <div className="flex items-center gap-2 text-[0.7rem]">
                <XCircle size={10} className="text-[#EF4444]" />
                <span className="text-[#374151]">35 failed</span>
              </div>
            </div>
          </div>
        </div>
        <div className="rounded-[12px] border border-[#E8EDF3] bg-white p-4 shadow-sm">
          <p className="text-[0.72rem] font-bold text-[#6B7280] mb-3 uppercase tracking-wider">Latency Trend</p>
          <LatencyBar latencyMs={latencyMs} />
          <div className="mt-3 space-y-1.5">
            <div className="flex justify-between text-[0.7rem]">
              <span className="text-[#6B7280]">P50</span>
              <span className="font-semibold text-[#111827]">{latencyMs ? Math.round(latencyMs * 0.8) : "--"}ms</span>
            </div>
            <div className="flex justify-between text-[0.7rem]">
              <span className="text-[#6B7280]">P95</span>
              <span className="font-semibold text-[#111827]">{latencyMs ? Math.round(latencyMs * 1.5) : "--"}ms</span>
            </div>
            <div className="flex justify-between text-[0.7rem]">
              <span className="text-[#6B7280]">P99</span>
              <span className="font-semibold text-[#111827]">{latencyMs ? Math.round(latencyMs * 2.2) : "--"}ms</span>
            </div>
          </div>
        </div>
      </div>

      {/* Activity graph */}
      <div className="rounded-[12px] border border-[#E8EDF3] bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <p className="text-[0.72rem] font-bold text-[#6B7280] uppercase tracking-wider">Activity (Last 24h)</p>
          <span className="text-[0.65rem] text-[#38B88A] font-semibold">+23% vs yesterday</span>
        </div>
        <ActivitySparkline />
        <div className="flex justify-between mt-1 text-[0.6rem] text-[#9CA3AF]">
          <span>00:00</span>
          <span>06:00</span>
          <span>12:00</span>
          <span>18:00</span>
          <span>Now</span>
        </div>
      </div>

      {/* Recent operations */}
      <div className="rounded-[12px] border border-[#E8EDF3] bg-white p-4 shadow-sm">
        <p className="text-[0.72rem] font-bold text-[#6B7280] mb-3 uppercase tracking-wider">Recent Operations</p>
        <div className="space-y-1">
          {recentOperations.map((op, i) => (
            <div key={i} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
              <div className="flex items-center gap-2">
                {op.status === "success" ? (
                  <CheckCircle size={12} className="text-[#38B88A]" />
                ) : (
                  <XCircle size={12} className="text-[#EF4444]" />
                )}
                <span className="text-[0.75rem] text-[#374151]">{op.op}</span>
              </div>
              <div className="flex items-center gap-3 text-[0.65rem] text-[#9CA3AF]">
                <span>{op.duration}</span>
                <span>{op.time}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Permissions summary */}
      <div className="rounded-[12px] border border-[#E8EDF3] bg-white p-4 shadow-sm">
        <div className="flex items-center gap-2 mb-3">
          <Shield size={14} className="text-[#38B88A]" />
          <p className="text-[0.72rem] font-bold text-[#6B7280] uppercase tracking-wider">Permissions</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {connector.permissions.map((perm) => (
            <span key={perm.key} className="inline-flex items-center gap-1 rounded-full bg-[#ECFBF4] px-2.5 py-1 text-[0.65rem] font-medium text-[#2F9F77]">
              <CheckCircle size={10} />
              {perm.label}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}
