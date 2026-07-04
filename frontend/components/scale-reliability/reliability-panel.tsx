"use client"

import { useState } from "react"
import {
  Shield,
  Clock,
  Activity,
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  Server,
  Database,
  Wifi,
  Cpu,
  TrendingUp,
  TrendingDown,
} from "lucide-react"
import { StatusBadge, KpiCard, SectionHeader, DataTable, GaugeChart } from "./shared"

const monthlySLA = [
  { month: "Jan", sla: 99.97 },
  { month: "Feb", sla: 99.95 },
  { month: "Mar", sla: 99.98 },
  { month: "Apr", sla: 99.93 },
  { month: "May", sla: 99.96 },
  { month: "Jun", sla: 99.91 },
  { month: "Jul", sla: 99.97 },
  { month: "Aug", sla: 99.99 },
  { month: "Sep", sla: 99.95 },
  { month: "Oct", sla: 99.98 },
  { month: "Nov", sla: 99.97 },
  { month: "Dec", sla: 99.97 },
]

const weeklyUptime = [
  { day: "Mon", uptime: 99.98 },
  { day: "Tue", uptime: 99.97 },
  { day: "Wed", uptime: 99.95 },
  { day: "Thu", uptime: 99.99 },
  { day: "Fri", uptime: 99.93 },
  { day: "Sat", uptime: 99.98 },
  { day: "Sun", uptime: 99.97 },
]

const incidents = [
  { date: "Jun 28, 2026", duration: "4m 12s", impact: "Mission execution delayed", rootCause: "Redis connection pool exhausted", resolution: "Increased pool size", status: "resolved" },
  { date: "Jun 26, 2026", duration: "2m 05s", impact: "API latency spike", rootCause: "Neo4j query timeout", resolution: "Optimized query + added index", status: "resolved" },
  { date: "Jun 24, 2026", duration: "1m 48s", impact: "Worker tasks queued", rootCause: "Worker pod OOM kill", resolution: "Increased memory limits", status: "resolved" },
  { date: "Jun 22, 2026", duration: "3m 30s", impact: "Connector timeout", rootCause: "Rate limiting on external API", resolution: "Added retry with backoff", status: "resolved" },
  { date: "Jun 20, 2026", duration: "5m 00s", impact: "Memory store unresponsive", rootCause: "Cache stampede on key expiry", resolution: "Staggered TTL + pre-warming", status: "resolved" },
  { date: "Jun 18, 2026", duration: "1m 15s", impact: "KG query failures", rootCause: "Neo4j leader re-election", resolution: "Added read replicas", status: "resolved" },
  { date: "Jun 16, 2026", duration: "—", impact: "Elevated error rate", rootCause: "Under investigation", resolution: "Monitoring active", status: "investigating" },
  { date: "Jun 14, 2026", duration: "2m 20s", impact: "LLM response delay", rootCause: "API provider throttling", resolution: "Added fallback provider", status: "resolved" },
]

const serviceIndicators = [
  { name: "API Gateway", sla: 99.99, status: "healthy" },
  { name: "Mission Runtime", sla: 99.97, status: "healthy" },
  { name: "Workers", sla: 99.95, status: "healthy" },
  { name: "Memory (Redis)", sla: 99.93, status: "degraded" },
  { name: "Knowledge Graph", sla: 99.96, status: "healthy" },
  { name: "Connectors", sla: 99.94, status: "healthy" },
]

const slaMax = 100
const slaMin = 99.85
const slaRange = slaMax - slaMin

const chartW = 500
const chartH = 140
const slaX = (i: number) => (i / (monthlySLA.length - 1)) * chartW
const slaY = (v: number) => chartH - ((v - slaMin) / slaRange) * chartH

const slaLinePath = monthlySLA
  .map((m, i) => `${i === 0 ? "M" : "L"}${slaX(i).toFixed(1)},${slaY(m.sla).toFixed(1)}`)
  .join(" ")

export default function ReliabilityPanel() {
  const [filter, setFilter] = useState<"all" | "resolved" | "investigating">("all")

  const filteredIncidents = incidents.filter((inc) => filter === "all" || inc.status === filter)

  return (
    <div className="space-y-6">
      <SectionHeader title="Reliability Dashboard" subtitle="System reliability and SLA compliance metrics" />

      <div className="grid grid-cols-6 gap-4">
        <KpiCard title="Availability" value="99.97%" change="+0.02%" icon={<Shield size={16} />} />
        <KpiCard title="SLA Compliance" value="99.95%" change="+0.01%" icon={<CheckCircle2 size={16} />} />
        <KpiCard title="MTTR" value="4.2min" change="-0.8min" icon={<Clock size={16} />} />
        <KpiCard title="MTBF" value="72h" change="+6h" icon={<Activity size={16} />} />
        <KpiCard title="Retry Rate" value="1.2%" change="-0.3%" icon={<RefreshCw size={16} />} />
        <KpiCard title="Recovery Rate" value="99.8%" change="+0.5%" icon={<TrendingUp size={16} />} />
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="bg-white rounded-[18px] border border-[#E8EDF3] p-5 shadow-sm">
          <SectionHeader title="Weekly Uptime" subtitle="Uptime percentage — last 7 days" />
          <div className="flex items-end gap-3 h-32 pt-4">
            {weeklyUptime.map((d) => {
              const h = ((d.uptime - 99.9) / 0.1) * 100
              return (
                <div key={d.day} className="flex-1 flex flex-col items-center gap-1 h-full justify-end">
                  <span className="text-[10px] text-gray-500 font-medium">{d.uptime.toFixed(2)}%</span>
                  <div
                    className="w-full rounded-lg transition-all"
                    style={{ height: `${Math.max(h, 10)}%`, backgroundColor: d.uptime >= 99.97 ? "#38B88A" : d.uptime >= 99.95 ? "#F59E0B" : "#EF4444" }}
                  />
                  <span className="text-[10px] text-gray-400">{d.day}</span>
                </div>
              )
            })}
          </div>
        </div>

        <div className="bg-white rounded-[18px] border border-[#E8EDF3] p-5 shadow-sm">
          <SectionHeader title="Monthly SLA Tracker" subtitle="SLA % over last 12 months" />
          <svg viewBox={`0 0 ${chartW} ${chartH + 20}`} className="w-full h-auto">
            <defs>
              <linearGradient id="slaGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#38B88A" stopOpacity={0.15} />
                <stop offset="100%" stopColor="#38B88A" stopOpacity={0} />
              </linearGradient>
            </defs>
            <path
              d={`${slaLinePath} L${slaX(monthlySLA.length - 1).toFixed(1)},${chartH} L${slaX(0).toFixed(1)},${chartH} Z`}
              fill="url(#slaGrad)"
            />
            <path d={slaLinePath} fill="none" stroke="#38B88A" strokeWidth={2} strokeLinecap="round" />
            <line x1={0} y1={slaY(99.95)} x2={chartW} y2={slaY(99.95)} stroke="#F59E0B" strokeWidth={1} strokeDasharray="4 3" />
            <text x={chartW} y={slaY(99.95) - 4} textAnchor="end" className="text-[9px] fill-amber-500">99.95% target</text>
            {monthlySLA.filter((_, i) => i % 2 === 0).map((m, i) => {
              const idx = monthlySLA.indexOf(m)
              return (
                <text key={idx} x={slaX(idx)} y={chartH + 14} textAnchor="middle" className="text-[9px] fill-gray-400">
                  {m.month}
                </text>
              )
            })}
          </svg>
        </div>
      </div>

      <div className="bg-white rounded-[18px] border border-[#E8EDF3] p-5 shadow-sm">
        <SectionHeader
          title="Incidents"
          subtitle="Recent reliability incidents"
          action={
            <div className="flex gap-1 bg-gray-100 rounded-lg p-0.5">
              {(["all", "resolved", "investigating"] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                    filter === f ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"
                  }`}
                >
                  {f.charAt(0).toUpperCase() + f.slice(1)}
                </button>
              ))}
            </div>
          }
        />
        <DataTable
          columns={[
            { key: "date", label: "Date" },
            { key: "duration", label: "Duration" },
            { key: "impact", label: "Impact" },
            { key: "rootCause", label: "Root Cause" },
            { key: "resolution", label: "Resolution" },
            {
              key: "status",
              label: "Status",
              render: (val: unknown) => <StatusBadge status={val as string} label={val as string} />,
            },
          ]}
          rows={filteredIncidents}
        />
      </div>

      <div className="bg-white rounded-[18px] border border-[#E8EDF3] p-5 shadow-sm">
        <SectionHeader title="Service-Level Indicators" subtitle="SLA compliance by component" />
        <div className="grid grid-cols-6 gap-4">
          {serviceIndicators.map((s) => (
            <div key={s.name} className="text-center p-3 rounded-xl border border-[#E8EDF3] hover:bg-gray-50 transition-colors">
              <GaugeChart value={Number(((s.sla - 99.9) / 0.1 * 100).toFixed(1))} max={100} size="md" label={s.name} color={s.status === "healthy" ? "#38B88A" : "#F59E0B"} />
              <div className="mt-1">
                <StatusBadge status={s.status} label={`${s.sla.toFixed(2)}%`} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}