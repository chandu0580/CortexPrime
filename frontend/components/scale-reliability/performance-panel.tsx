"use client"

import { useState } from "react"
import {
  Activity,
  ArrowUp,
  ArrowDown,
  Zap,
  Cpu,
  HardDrive,
  Globe,
  Server,
  Database,
  MessageSquare,
  Wifi,
  ChevronRight,
} from "lucide-react"
import { StatusBadge, KpiCard, ProgressBar, SectionHeader, ResourceBar } from "./shared"

const throughputData = Array.from({ length: 30 }, (_, i) => ({
  value: 120 + Math.sin(i * 0.3) * 30 + Math.random() * 20 + (i > 20 ? 10 : 0),
  label: `T-${29 - i}`,
}))

const chartW = 600
const chartH = 120
const chartPad = { top: 10, bottom: 20, left: 0, right: 0 }
const chartYMin = Math.min(...throughputData.map((d) => d.value)) - 10
const chartYMax = Math.max(...throughputData.map((d) => d.value)) + 10

const xScale = (i: number) => chartPad.left + (i / (throughputData.length - 1)) * (chartW - chartPad.left - chartPad.right)
const yScale = (v: number) => chartPad.top + chartH - chartPad.bottom - ((v - chartYMin) / (chartYMax - chartYMin)) * (chartH - chartPad.top - chartPad.bottom)

const linePath = throughputData
  .map((d, i) => `${i === 0 ? "M" : "L"}${xScale(i).toFixed(1)},${yScale(d.value).toFixed(1)}`)
  .join(" ")

const areaPath = `${linePath} L${xScale(throughputData.length - 1).toFixed(1)},${(chartH - chartPad.bottom).toFixed(1)} L${xScale(0).toFixed(1)},${(chartH - chartPad.bottom).toFixed(1)} Z`

const resources = [
  { label: "CPU", used: 62, total: 100, color: "#38B88A" },
  { label: "Memory", used: 74, total: 100, color: "#F59E0B" },
  { label: "Storage", used: 41, total: 100, color: "#38B88A" },
  { label: "Network", used: 38, total: 100, color: "#3B82F6" },
  { label: "GPU", used: 28, total: 100, color: "#8B5CF6" },
]

const componentStatuses = [
  { name: "API Gateway", status: "healthy" },
  { name: "Mission Runtime", status: "healthy" },
  { name: "EventBus", status: "healthy" },
  { name: "Redis", status: "healthy" },
  { name: "PostgreSQL", status: "degraded" },
  { name: "Neo4j", status: "healthy" },
  { name: "RabbitMQ", status: "healthy" },
  { name: "Prometheus", status: "healthy" },
]

export default function PerformancePanel() {
  const [selectedMetric, setSelectedMetric] = useState("throughput")

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Performance Dashboard"
        subtitle="Real-time system performance metrics"
        action={
          <div className="flex gap-1 bg-gray-100 rounded-lg p-0.5">
            <button
              onClick={() => setSelectedMetric("throughput")}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                selectedMetric === "throughput" ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"
              }`}
            >
              Throughput
            </button>
            <button
              onClick={() => setSelectedMetric("latency")}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                selectedMetric === "latency" ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"
              }`}
            >
              Latency
            </button>
            <button
              onClick={() => setSelectedMetric("resources")}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                selectedMetric === "resources" ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"
              }`}
            >
              Resources
            </button>
          </div>
        }
      />

      <div className="grid grid-cols-4 gap-4">
        <KpiCard
          title="Mission Throughput"
          value="142/min"
          change="+12%"
          icon={<Activity size={16} />}
        />
        <KpiCard
          title="Worker Throughput"
          value="856/min"
          change="+8%"
          icon={<Zap size={16} />}
        />
        <KpiCard
          title="API Throughput"
          value="2,341/min"
          change="+15%"
          icon={<Globe size={16} />}
        />
        <KpiCard
          title="Memory Latency"
          value="4.2ms"
          change="-0.3ms"
          icon={<Cpu size={16} />}
        />
        <KpiCard
          title="KG Latency"
          value="12.8ms"
          change="-1.2ms"
          icon={<Database size={16} />}
        />
        <KpiCard
          title="Connector Latency"
          value="187ms"
          change="-23ms"
          icon={<Wifi size={16} />}
        />
        <KpiCard
          title="LLM Latency"
          value="1,240ms"
          change="+45ms"
          icon={<MessageSquare size={16} />}
        />
        <KpiCard
          title="Resource Utilization"
          value="67%"
          subtitle="avg across all nodes"
          icon={<Server size={16} />}
        />
      </div>

      <div className="grid grid-cols-3 gap-6">
        <div className="bg-white rounded-[18px] border border-[#E8EDF3] p-5 shadow-sm col-span-2">
          <SectionHeader
            title="Throughput Trend"
            subtitle="Last 30 data points — mission throughput (req/min)"
          />
          <svg viewBox={`0 0 ${chartW} ${chartH}`} className="w-full h-auto" preserveAspectRatio="xMidYMid meet">
            <defs>
              <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#38B88A" stopOpacity={0.2} />
                <stop offset="100%" stopColor="#38B88A" stopOpacity={0} />
              </linearGradient>
            </defs>
            <path d={areaPath} fill="url(#areaGrad)" />
            <path d={linePath} fill="none" stroke="#38B88A" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
            {throughputData.filter((_, i) => i % 5 === 0 || i === throughputData.length - 1).map((d, i, arr) => {
              const idx = throughputData.indexOf(d)
              return (
                <g key={idx}>
                  <text x={xScale(idx)} y={chartH - 4} textAnchor="middle" className="text-[10px] fill-gray-400">
                    {d.label}
                  </text>
                </g>
              )
            })}
            <text x={xScale(throughputData.length - 1)} y={yScale(throughputData[throughputData.length - 1].value) - 8} textAnchor="end" className="text-[10px] fill-[#38B88A] font-medium">
              {throughputData[throughputData.length - 1].value.toFixed(0)}
            </text>
          </svg>
          <div className="flex items-center gap-4 mt-3 text-xs text-gray-500">
            <span className="flex items-center gap-1">
              <span className="w-3 h-0.5 bg-[#38B88A] rounded-full inline-block" /> Mission Throughput
            </span>
            <span className="flex items-center gap-1 text-emerald-600 font-medium">
              <ArrowUp size={12} /> +12% from last period
            </span>
          </div>
        </div>

        <div className="bg-white rounded-[18px] border border-[#E8EDF3] p-5 shadow-sm">
          <SectionHeader title="Resource Utilization" />
          <div className="space-y-3">
            {resources.map((r) => (
              <ResourceBar key={r.label} label={r.label} used={r.used} total={r.total} unit="%" color={r.color} />
            ))}
          </div>
        </div>
      </div>

      <div className="bg-white rounded-[18px] border border-[#E8EDF3] p-5 shadow-sm">
        <SectionHeader title="System Health" subtitle="Component status overview" />
        <div className="grid grid-cols-4 gap-3">
          {componentStatuses.map((c) => (
            <div
              key={c.name}
              className="flex items-center justify-between p-3 rounded-xl border border-[#E8EDF3] hover:bg-gray-50 transition-colors cursor-pointer"
            >
              <span className="text-sm font-medium text-gray-700">{c.name}</span>
              <StatusBadge status={c.status} label={c.status} />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}