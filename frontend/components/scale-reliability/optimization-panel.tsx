"use client"

import { useState } from "react"
import {
  Cpu,
  HardDrive,
  Server,
  Database,
  Wifi,
  DollarSign,
  CheckCircle2,
  AlertTriangle,
  TrendingDown,
  Lightbulb,
  Zap,
  Shield,
} from "lucide-react"
import { StatusBadge, KpiCard, SectionHeader, DataTable } from "./shared"

const recommendations = [
  {
    category: "CPU",
    current: "64 cores",
    recommended: "48 cores",
    savings: "25%",
    risk: "Low",
    impact: "Reduces over-provisioning; workloads peak at 38 cores",
  },
  {
    category: "Memory",
    current: "256 GB",
    recommended: "192 GB",
    savings: "25%",
    risk: "Low",
    impact: "Current usage averages 140 GB with 256 GB allocated",
  },
  {
    category: "Workers",
    current: "24",
    recommended: "18",
    savings: "25%",
    risk: "Medium",
    impact: "Idle workers consume resources; auto-scaling covers peaks",
  },
  {
    category: "Connector Pools",
    current: "8 × 10",
    recommended: "8 × 6",
    savings: "40%",
    risk: "Medium",
    impact: "Pool utilization averages 4.2 connections per pool",
  },
  {
    category: "Redis",
    current: "cache.m6g.4xlarge",
    recommended: "cache.m6g.2xlarge",
    savings: "50%",
    risk: "Low",
    impact: "Cache hit rate is 94%; current capacity underutilized",
  },
  {
    category: "Neo4j",
    current: "r5.4xlarge",
    recommended: "r5.2xlarge",
    savings: "50%",
    risk: "Medium",
    impact: "Query volume supports downsize; monitor during peak",
  },
  {
    category: "K8s Replicas",
    current: "12",
    recommended: "9",
    savings: "25%",
    risk: "Low",
    impact: "HPA handles spikes; 9 replicas sufficient for baseline",
  },
]

const riskColors: Record<string, string> = {
  Low: "#38B88A",
  Medium: "#F59E0B",
  High: "#EF4444",
}

export default function OptimizationPanel() {
  const [applied, setApplied] = useState(false)

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Resource Optimization"
        subtitle="Identify underutilized resources and reduce costs"
        action={
          !applied ? (
            <button
              onClick={() => setApplied(true)}
              className="px-5 py-2 bg-[#38B88A] hover:bg-emerald-600 text-white text-sm font-semibold rounded-xl transition-colors flex items-center gap-2"
            >
              <Zap size={16} /> Apply Recommendations
            </button>
          ) : (
            <StatusBadge status="healthy" label="Applied" />
          )
        }
      />

      {applied && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 flex items-center gap-3">
          <CheckCircle2 size={20} className="text-emerald-600" />
          <div>
            <span className="text-sm font-semibold text-emerald-800">Recommendations Applied</span>
            <p className="text-xs text-emerald-600">Changes are being rolled out gradually. Monitor for 24 hours.</p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-4 gap-4">
        <KpiCard title="Current Monthly Cost" value="$13,220" change="" icon={<DollarSign size={16} />} />
        <KpiCard title="Optimized Monthly Cost" value={applied ? "$8,990" : "$8,990"} icon={<TrendingDown size={16} />} color="#38B88A" />
        <KpiCard title="Monthly Savings" value="$4,230" change="32% reduction" icon={applied ? <CheckCircle2 size={16} /> : <Lightbulb size={16} />} color="#38B88A" />
        <KpiCard title="Risk Level" value="Low" icon={<Shield size={16} />} color="#38B88A" />
      </div>

      <div className="bg-white rounded-[18px] border border-[#E8EDF3] p-5 shadow-sm">
        <SectionHeader title="Optimization Recommendations" subtitle="Current vs Recommended resource allocation" />
        <DataTable
          columns={[
            { key: "category", label: "Category" },
            { key: "current", label: "Current" },
            { key: "recommended", label: "Recommended" },
            { key: "savings", label: "Savings" },
            {
              key: "risk",
              label: "Risk",
              render: (val: unknown) => (
                <span className="inline-flex items-center gap-1 text-xs font-medium" style={{ color: riskColors[val as string] || "#6B7280" }}>
                  <span className="w-1.5 h-1.5 rounded-full inline-block" style={{ backgroundColor: riskColors[val as string] || "#6B7280" }} />
                  {val as string}
                </span>
              ),
            },
            { key: "impact", label: "Impact Assessment" },
          ]}
          rows={recommendations}
        />
      </div>

      <div className="grid grid-cols-4 gap-4">
        {recommendations.slice(0, 4).map((r) => (
          <div
            key={r.category}
            className="bg-white rounded-[18px] border border-[#E8EDF3] p-4 shadow-sm hover:border-[#38B88A] hover:shadow-md transition-all"
          >
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-semibold text-gray-500 uppercase">{r.category}</span>
              <StatusBadge status={r.risk === "Low" ? "healthy" : r.risk === "Medium" ? "warning" : "error"} label={r.risk} />
            </div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-gray-400">Current</span>
              <span className="text-xs text-gray-900 line-through">{r.current}</span>
            </div>
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs text-emerald-600 font-medium">Recommended</span>
              <span className="text-sm font-bold text-emerald-700">{r.recommended}</span>
            </div>
            <div className="p-2 rounded-lg bg-emerald-50 border border-emerald-100 text-center">
              <span className="text-xs font-semibold text-emerald-700">Save {r.savings}</span>
            </div>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-[18px] border border-[#E8EDF3] p-5 shadow-sm">
        <SectionHeader title="Risk Assessment" subtitle="Detailed risk evaluation per recommendation" />
        <div className="space-y-3">
          {recommendations.map((r) => (
            <div key={r.category} className="flex items-start gap-4 p-3 rounded-xl border border-[#E8EDF3] hover:bg-gray-50 transition-colors">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0" style={{ backgroundColor: `${riskColors[r.risk]}15` }}>
                {r.category === "CPU" ? <Cpu size={16} style={{ color: riskColors[r.risk] }} /> :
                 r.category === "Memory" ? <HardDrive size={16} style={{ color: riskColors[r.risk] }} /> :
                 r.category === "Workers" ? <Server size={16} style={{ color: riskColors[r.risk] }} /> :
                 r.category === "Connector Pools" ? <Wifi size={16} style={{ color: riskColors[r.risk] }} /> :
                 r.category === "Redis" || r.category === "Neo4j" ? <Database size={16} style={{ color: riskColors[r.risk] }} /> :
                 <Server size={16} style={{ color: riskColors[r.risk] }} />}
              </div>
              <div className="flex-1">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-gray-900">{r.category}</span>
                  <span className="text-xs font-medium" style={{ color: riskColors[r.risk] }}>
                    {r.risk} Risk
                  </span>
                </div>
                <p className="text-xs text-gray-500 mt-0.5">{r.impact}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}