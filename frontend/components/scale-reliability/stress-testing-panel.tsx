"use client"

import { useState } from "react"
import {
  Activity,
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  Zap,
  Database,
  MessageSquare,
  Server,
  Lightbulb,
  Shield,
  Play,
} from "lucide-react"
import { StatusBadge, KpiCard, SectionHeader, DataTable } from "./shared"

const bottlenecks = [
  { rank: "1st", component: "Neo4j write contention", threshold: "at 1,800 TPS", severity: "critical" },
  { rank: "2nd", component: "LLM rate limiting", threshold: "at 2,100 TPS", severity: "warning" },
  { rank: "3rd", component: "PostgreSQL connection pool", threshold: "at 2,300 TPS", severity: "warning" },
]

const recommendations = [
  { title: "Scale Neo4j to 3 nodes", impact: "High", effort: "Medium", category: "Database" },
  { title: "Increase LLM rate limits", impact: "High", effort: "Low", category: "API" },
  { title: "Increase PG pool to 50", impact: "Medium", effort: "Low", category: "Database" },
  { title: "Add Redis read replicas", impact: "Medium", effort: "Medium", category: "Cache" },
]

const chartW = 500
const chartH = 160
const recoveryPoints = [
  { t: "0s", v: 2450 },
  { t: "5s", v: 2100 },
  { t: "10s", v: 1200 },
  { t: "15s", v: 800 },
  { t: "20s", v: 1450 },
  { t: "25s", v: 1900 },
  { t: "30s", v: 2200 },
  { t: "35s", v: 2350 },
  { t: "40s", v: 2400 },
]
const rYMin = Math.min(...recoveryPoints.map((p) => p.v)) - 200
const rYMax = Math.max(...recoveryPoints.map((p) => p.v)) + 200

const rX = (i: number) => (i / (recoveryPoints.length - 1)) * chartW
const rY = (v: number) => chartH - ((v - rYMin) / (rYMax - rYMin)) * chartH

const rLinePath = recoveryPoints
  .map((p, i) => `${i === 0 ? "M" : "L"}${rX(i).toFixed(1)},${rY(p.v).toFixed(1)}`)
  .join(" ")

export default function StressTestingPanel() {
  const [running, setRunning] = useState(false)
  const [completed, setCompleted] = useState(false)

  const runStressTest = () => {
    setRunning(true)
    setCompleted(false)
    setTimeout(() => {
      setRunning(false)
      setCompleted(true)
    }, 3000)
  }

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Stress Testing"
        subtitle="Push the system to its breaking point"
        action={
          !running ? (
            <button
              onClick={runStressTest}
              className="px-5 py-2 bg-red-500 hover:bg-red-600 text-white text-sm font-semibold rounded-xl transition-colors flex items-center gap-2"
            >
              <Play size={16} /> Run Stress Test
            </button>
          ) : (
            <span className="text-sm text-amber-600 font-medium flex items-center gap-1.5">
              <Activity size={14} className="animate-pulse" /> Stress testing in progress...
            </span>
          )
        }
      />

      {running && (
        <div className="bg-white rounded-[18px] border border-[#E8EDF3] p-8 shadow-sm flex items-center justify-center">
          <div className="text-center">
            <Activity size={40} className="text-[#38B88A] animate-pulse mx-auto mb-3" />
            <p className="text-sm text-gray-600">Gradually increasing load...</p>
            <p className="text-xs text-gray-400 mt-1">Starting at 100 TPS, +50 TPS every 2s</p>
          </div>
        </div>
      )}

      {completed && (
        <>
          <div className="bg-white rounded-[18px] border border-[#E8EDF3] p-5 shadow-sm">
            <SectionHeader
              title="Breaking Point Analysis"
              subtitle="Maximum achieved metrics before system degradation"
              action={<StatusBadge status="healthy" label="Test Complete" />}
            />
            <div className="grid grid-cols-4 gap-4">
              <KpiCard title="Max TPS" value="2,450" icon={<Zap size={16} color="#EF4444" />} />
              <KpiCard title="Max Concurrent Missions" value="87" icon={<Activity size={16} color="#F59E0B" />} />
              <KpiCard title="Max Concurrent Workers" value="42" icon={<Server size={16} color="#3B82F6" />} />
              <KpiCard title="Max API Calls" value="18,432/min" icon={<TrendingUp size={16} color="#38B88A" />} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-6">
            <div className="bg-white rounded-[18px] border border-[#E8EDF3] p-5 shadow-sm">
              <SectionHeader title="Bottlenecks Identified" />
              <div className="space-y-3">
                {bottlenecks.map((b) => (
                  <div
                    key={b.rank}
                    className="flex items-center justify-between p-3 rounded-xl border border-[#E8EDF3] hover:bg-gray-50"
                  >
                    <div className="flex items-center gap-3">
                      <span
                        className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-white ${
                          b.severity === "critical" ? "bg-red-500" : "bg-amber-500"
                        }`}
                      >
                        {b.rank.replace(/[a-z]/g, "")}
                      </span>
                      <div>
                        <span className="text-sm font-medium text-gray-900">{b.component}</span>
                        <p className="text-xs text-gray-400">{b.threshold}</p>
                      </div>
                    </div>
                    <StatusBadge status={b.severity} label={b.severity} />
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-white rounded-[18px] border border-[#E8EDF3] p-5 shadow-sm">
              <SectionHeader title="Recovery Behavior" subtitle="TPS drop and recovery over time" />
              <svg viewBox={`0 0 ${chartW} ${chartH}`} className="w-full h-auto">
                <defs>
                  <linearGradient id="recGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#EF4444" stopOpacity={0.15} />
                    <stop offset="100%" stopColor="#EF4444" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <path
                  d={`${rLinePath} L${rX(recoveryPoints.length - 1).toFixed(1)},${chartH} L${rX(0).toFixed(1)},${chartH} Z`}
                  fill="url(#recGrad)"
                />
                <path d={rLinePath} fill="none" stroke="#EF4444" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
                {recoveryPoints.map((p, i) => (
                  <g key={i}>
                    <circle cx={rX(i)} cy={rY(p.v)} r={3} fill="#EF4444" />
                    {i % 2 === 0 && (
                      <text x={rX(i)} y={chartH + 12} textAnchor="middle" className="text-[9px] fill-gray-400">
                        {p.t}
                      </text>
                    )}
                  </g>
                ))}
              </svg>
              <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
                <span className="flex items-center gap-1">
                  <span className="w-3 h-0.5 bg-red-400 rounded-full inline-block" /> TPS
                </span>
                <span className="text-emerald-600 flex items-center gap-1">
                  <TrendingUp size={12} /> Recovered at 40s
                </span>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-[18px] border border-[#E8EDF3] p-5 shadow-sm">
            <SectionHeader title="System Recommendations" />
            <div className="grid grid-cols-4 gap-4">
              {recommendations.map((r) => (
                <div
                  key={r.title}
                  className="p-4 rounded-xl border border-[#E8EDF3] hover:border-[#38B88A] hover:bg-emerald-50/20 transition-all cursor-pointer"
                >
                  <div className="flex items-center gap-2 mb-2">
                    <Lightbulb size={16} className="text-[#38B88A]" />
                    <span className="text-xs font-medium text-[#38B88A]">{r.category}</span>
                  </div>
                  <p className="text-sm font-semibold text-gray-900 mb-2">{r.title}</p>
                  <div className="flex gap-2">
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                        r.impact === "High" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"
                      }`}
                    >
                      {r.impact} Impact
                    </span>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 font-medium">
                      {r.effort} Effort
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="flex items-center justify-between p-4 rounded-xl bg-gray-50 border border-[#E8EDF3]">
            <div className="flex items-center gap-3">
              <Shield size={20} className="text-[#38B88A]" />
              <div>
                <span className="text-sm font-semibold text-gray-900">Last Stress Test</span>
                <p className="text-xs text-gray-400">Completed at {new Date().toLocaleString()} · System fully recovered</p>
              </div>
            </div>
            <StatusBadge status="healthy" label="Stable" />
          </div>
        </>
      )}

      {!running && !completed && (
        <div className="bg-white rounded-[18px] border border-[#E8EDF3] p-8 shadow-sm flex items-center justify-center">
          <div className="text-center max-w-md">
            <AlertTriangle size={40} className="text-gray-300 mx-auto mb-3" />
            <h4 className="text-base font-semibold text-gray-700 mb-1">No Test Data</h4>
            <p className="text-xs text-gray-400">
              Run a stress test to identify system breaking points, bottlenecks, and get optimization recommendations.
            </p>
          </div>
        </div>
      )}
    </div>
  )
}