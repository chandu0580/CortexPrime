"use client"

import { useState } from "react"
import {
  Database,
  Server,
  MessageSquare,
  Activity,
  Wifi,
  Timer,
  AlertTriangle,
  CheckCircle2,
  TrendingUp,
  Shield,
  Skull,
  Zap,
} from "lucide-react"
import { StatusBadge, KpiCard, SectionHeader, DataTable } from "./shared"

interface FailureScenario {
  id: string
  icon: typeof Database
  title: string
  description: string
  color: string
  lastResult: "passed" | "failed" | null
}

const failureScenarios: FailureScenario[] = [
  { id: "redis", icon: Database, title: "Redis Outage", description: "Simulate Redis cache cluster failure", color: "#EF4444", lastResult: "passed" },
  { id: "neo4j", icon: Database, title: "Neo4j Outage", description: "Simulate Neo4j graph database failure", color: "#F59E0B", lastResult: "passed" },
  { id: "rabbitmq", icon: MessageSquare, title: "RabbitMQ Outage", description: "Simulate message broker failure", color: "#EF4444", lastResult: "passed" },
  { id: "worker", icon: Server, title: "Worker Crash", description: "Simulate random worker pod crash", color: "#8B5CF6", lastResult: "failed" },
  { id: "connector", icon: Wifi, title: "Connector Outage", description: "Simulate external connector failure", color: "#3B82F6", lastResult: null },
  { id: "mission", icon: Activity, title: "Mission Timeout", description: "Simulate mission execution timeout", color: "#38B88A", lastResult: "passed" },
  { id: "llm", icon: MessageSquare, title: "LLM Timeout", description: "Simulate LLM API timeout", color: "#F59E0B", lastResult: null },
]

const recoveryMetrics = {
  detectTime: "1.2s",
  recoverTime: "4.5s",
  strategy: "Automatic failover",
  impact: "342ms latency increase",
  dataLoss: "None",
}

const failureHistory = [
  { date: "Jun 28", scenario: "Redis Outage", result: "Recovered in 3.2s", status: "passed" },
  { date: "Jun 26", scenario: "Worker Crash", result: "Recovered in 5.8s", status: "passed" },
  { date: "Jun 24", scenario: "Neo4j Outage", result: "Recovered in 4.1s", status: "passed" },
  { date: "Jun 22", scenario: "Connector Outage", result: "Recovered in 6.3s", status: "passed" },
  { date: "Jun 20", scenario: "Worker Crash", result: "Manual intervention required", status: "failed" },
  { date: "Jun 18", scenario: "Mission Timeout", result: "Recovered in 1.5s", status: "passed" },
  { date: "Jun 16", scenario: "RabbitMQ Outage", result: "Recovered in 2.9s", status: "passed" },
]

const chartW = 500
const chartH = 140
const dipPoints = [
  { t: "-5s", v: 120 },
  { t: "-3s", v: 118 },
  { t: "0s", v: 42 },
  { t: "1s", v: 28 },
  { t: "2s", v: 35 },
  { t: "3s", v: 55 },
  { t: "4s", v: 78 },
  { t: "5s", v: 95 },
  { t: "6s", v: 108 },
  { t: "8s", v: 116 },
  { t: "10s", v: 120 },
]

const dYMin = Math.min(...dipPoints.map((p) => p.v)) - 10
const dYMax = Math.max(...dipPoints.map((p) => p.v)) + 10
const dX = (i: number) => (i / (dipPoints.length - 1)) * chartW
const dY = (v: number) => chartH - ((v - dYMin) / (dYMax - dYMin)) * chartH

const dipLinePath = dipPoints
  .map((p, i) => `${i === 0 ? "M" : "L"}${dX(i).toFixed(1)},${dY(p.v).toFixed(1)}`)
  .join(" ")

export default function FailureInjectionPanel() {
  const [injectedScenario, setInjectedScenario] = useState<string | null>(null)
  const [injecting, setInjecting] = useState(false)

  const inject = (id: string) => {
    setInjecting(true)
    setInjectedScenario(id)
    setTimeout(() => {
      setInjecting(false)
    }, 2500)
  }

  return (
    <div className="space-y-6">
      <SectionHeader title="Failure Injection" subtitle="Test system resilience through controlled failure scenarios" />

      <div className="grid grid-cols-4 gap-4">
        {failureScenarios.map((scenario) => {
          const Icon = scenario.icon
          const isActive = injectedScenario === scenario.id
          return (
            <div
              key={scenario.id}
              className={`bg-white rounded-[18px] border p-5 shadow-sm transition-all ${
                isActive ? "border-amber-400 ring-2 ring-amber-200" : "border-[#E8EDF3] hover:border-gray-300"
              }`}
            >
              <div className="flex items-start justify-between mb-3">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ backgroundColor: `${scenario.color}15` }}>
                  <Icon size={18} style={{ color: scenario.color }} />
                </div>
                {scenario.lastResult && (
                  <StatusBadge status={scenario.lastResult === "passed" ? "healthy" : "error"} label={scenario.lastResult === "passed" ? "Passed" : "Failed"} />
                )}
              </div>
              <h4 className="text-sm font-semibold text-gray-900 mb-0.5">{scenario.title}</h4>
              <p className="text-xs text-gray-400 mb-3">{scenario.description}</p>
              <button
                onClick={() => inject(scenario.id)}
                disabled={injecting}
                className={`w-full py-2 text-xs font-semibold rounded-xl border transition-colors ${
                  injecting
                    ? "bg-gray-100 text-gray-400 border-gray-200 cursor-not-allowed"
                    : "border-[#E8EDF3] text-gray-700 hover:border-red-300 hover:text-red-600 hover:bg-red-50"
                }`}
              >
                {injecting && isActive ? "Injecting..." : "Inject"}
              </button>
            </div>
          )
        })}
      </div>

      {injectedScenario && (
        <>
          <div className="bg-white rounded-[18px] border border-[#E8EDF3] p-5 shadow-sm">
            <SectionHeader
              title="Recovery Metrics"
              subtitle={`Recovery analysis for ${failureScenarios.find((s) => s.id === injectedScenario)?.title || ""}`}
              action={<StatusBadge status={injecting ? "injecting" : "recovered"} label={injecting ? "Recovering..." : "Recovered"} />}
            />
            <div className="grid grid-cols-5 gap-4">
              <KpiCard title="Time to Detect" value={recoveryMetrics.detectTime} icon={<Timer size={16} />} />
              <KpiCard title="Time to Recover" value={recoveryMetrics.recoverTime} icon={<Activity size={16} />} />
              <KpiCard title="Recovery Strategy" value={recoveryMetrics.strategy} icon={<CheckCircle2 size={16} />} />
              <KpiCard title="Service Impact" value={recoveryMetrics.impact} icon={<AlertTriangle size={16} />} />
              <KpiCard title="Data Loss" value={recoveryMetrics.dataLoss} icon={<Database size={16} />} color={injecting ? "#F59E0B" : "#38B88A"} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-6">
            <div className="bg-white rounded-[18px] border border-[#E8EDF3] p-5 shadow-sm">
              <SectionHeader title="Recovery Timeline" subtitle="TPS dip and recovery curve" />
              <svg viewBox={`0 0 ${chartW} ${chartH}`} className="w-full h-auto">
                <defs>
                  <linearGradient id="dipGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#F59E0B" stopOpacity={0.15} />
                    <stop offset="100%" stopColor="#F59E0B" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <path
                  d={`${dipLinePath} L${dX(dipPoints.length - 1).toFixed(1)},${chartH} L${dX(0).toFixed(1)},${chartH} Z`}
                  fill="url(#dipGrad)"
                />
                <path d={dipLinePath} fill="none" stroke="#F59E0B" strokeWidth={2} strokeLinecap="round" />
                {dipPoints.map((p, i) => (
                  <g key={i}>
                    <circle cx={dX(i)} cy={dY(p.v)} r={3} fill="#F59E0B" />
                    {[0, 3, 6, 10].includes(i) && (
                      <text x={dX(i)} y={chartH + 12} textAnchor="middle" className="text-[9px] fill-gray-400">
                        {p.t}
                      </text>
                    )}
                  </g>
                ))}
              </svg>
              <div className="flex items-center gap-2 mt-2 text-xs text-gray-500">
                <span className="flex items-center gap-1">
                  <span className="w-3 h-0.5 bg-amber-400 rounded-full inline-block" /> TPS
                </span>
                <span className="text-emerald-600 flex items-center gap-1">
                  <TrendingUp size={12} /> Full recovery at +10s
                </span>
              </div>
            </div>

            <div className="bg-white rounded-[18px] border border-[#E8EDF3] p-5 shadow-sm">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-base font-semibold text-gray-900">Resilience Score</h3>
                  <p className="text-xs text-gray-400 mt-0.5">Overall system fault tolerance</p>
                </div>
              </div>
              <div className="flex items-center justify-center py-4">
                <div className="relative w-32 h-32">
                  <svg viewBox="0 0 120 120" className="w-full h-full">
                    <circle cx="60" cy="60" r="50" fill="none" stroke="#E8EDF3" strokeWidth="8" />
                    <circle
                      cx="60"
                      cy="60"
                      r="50"
                      fill="none"
                      stroke="#38B88A"
                      strokeWidth="8"
                      strokeDasharray={2 * Math.PI * 50}
                      strokeDashoffset={2 * Math.PI * 50 * (1 - 0.96)}
                      strokeLinecap="round"
                      transform="rotate(-90 60 60)"
                    />
                    <text x="60" y="55" textAnchor="middle" className="text-2xl font-bold fill-gray-900" dominantBaseline="central">
                      96
                    </text>
                    <text x="60" y="78" textAnchor="middle" className="text-xs fill-gray-400" dominantBaseline="central">
                      /100
                    </text>
                  </svg>
                  <div className="absolute inset-0 flex items-center justify-center pointer-events-none" />
                </div>
              </div>
              <div className="flex justify-center">
                <StatusBadge status="healthy" label="Highly Resilient" />
              </div>
            </div>
          </div>

          <div className="bg-white rounded-[18px] border border-[#E8EDF3] p-5 shadow-sm">
            <SectionHeader title="7-Day Failure History" subtitle="Recent failure injection test results" />
            <DataTable
              columns={[
                { key: "date", label: "Date" },
                { key: "scenario", label: "Scenario" },
                { key: "result", label: "Result" },
                {
                  key: "status",
                  label: "Status",
                  render: (val: unknown) => <StatusBadge status={val as string} label={val as string} />,
                },
              ]}
              rows={failureHistory}
            />
          </div>
        </>
      )}

      {!injectedScenario && (
        <div className="bg-white rounded-[18px] border border-[#E8EDF3] p-8 shadow-sm flex items-center justify-center">
          <div className="text-center max-w-md">
            <Shield size={40} className="text-gray-300 mx-auto mb-3" />
            <h4 className="text-base font-semibold text-gray-700 mb-1">No Active Injections</h4>
            <p className="text-xs text-gray-400">
              Click "Inject" on any failure scenario above to test system resilience and observe recovery behavior.
            </p>
          </div>
        </div>
      )}
    </div>
  )
}