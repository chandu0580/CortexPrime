"use client"

import { useEffect, useState } from "react"
import { TrendingUp, Crosshair, Activity, DollarSign, Zap } from "lucide-react"

type AnalyticsData = { missions: number; agents: number; avgLatency: number; costToday: number; successRate: number }

export default function AnalyticsCenter() {
  const [data, setData] = useState<AnalyticsData>({ missions: 0, agents: 0, avgLatency: 0, costToday: 0, successRate: 0 })

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch("/api/executive/analytics")
        const json = await res.json()
        setData({
          missions: json.totalMissions || 0,
          agents: json.totalAgents || 0,
          avgLatency: json.avgLatencyMs || 0,
          costToday: json.todayCost || 0,
          successRate: json.successRate || 0,
        })
      } catch { /* use defaults */ }
    }
    fetchData()
  }, [])

  const metrics = [
    { label: "Total Missions", value: data.missions.toString(), icon: Crosshair, color: "text-emerald-400" },
    { label: "Success Rate", value: `${(data.successRate * 100).toFixed(0)}%`, icon: TrendingUp, color: "text-blue-400" },
    { label: "Avg Latency", value: `${data.avgLatency.toFixed(0)}ms`, icon: Zap, color: "text-amber-400" },
    { label: "Cost Today", value: `$${data.costToday.toFixed(2)}`, icon: DollarSign, color: "text-violet-400" },
    { label: "Active Agents", value: data.agents.toString(), icon: Activity, color: "text-cyan-400" },
  ]

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Analytics</h1>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {metrics.map((m) => (
          <div key={m.label} className="border border-white/5 rounded-xl p-4 bg-white/[0.02]">
            <div className="flex items-center gap-2 text-xs text-white/40 mb-2">
              <m.icon className={`w-3.5 h-3.5 ${m.color}`} />
              {m.label}
            </div>
            <div className={`text-lg font-semibold ${m.color}`}>{m.value}</div>
          </div>
        ))}
      </div>
      <div className="border border-white/5 rounded-xl p-4 bg-white/[0.02]">
        <h2 className="text-sm font-medium text-white/60 mb-3">Mission Analytics</h2>
        <div className="flex items-center justify-center h-48">
          <p className="text-sm text-white/20">Connect to analytics backend and Prometheus for live charts</p>
        </div>
      </div>
    </div>
  )
}