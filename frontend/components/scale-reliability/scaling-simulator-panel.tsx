"use client"

import { useState } from "react"
import {
  Users,
  Activity,
  Server,
  Cpu,
  HardDrive,
  Database,
  DollarSign,
  BarChart3,
  Play,
  TrendingUp,
  Lightbulb,
  Wifi,
} from "lucide-react"
import { KpiCard, SectionHeader, ProgressBar } from "./shared"

interface ScalingResult {
  backendPods: number
  frontendPods: number
  workerPods: number
  totalPods: number
  cpuCores: number
  memoryGB: number
  storageTB: number
  redisType: string
  redisMem: string
  redisNodes: number
  neo4jType: string
  neo4jMem: string
  neo4jNodes: number
  monthlyCost: string
  costBreakdown: { compute: number; memory: number; storage: number; database: number; network: number }
}

function calculateScaling(users: number, missionsPerHour: number, workers: number, avgDuration: number): ScalingResult {
  const loadFactor = users / 1000 + missionsPerHour / 1000 + workers / 50 + avgDuration / 30
  const base = loadFactor * 0.8 + 0.2

  const backendPods = Math.max(2, Math.round(2 * base))
  const frontendPods = Math.max(1, Math.round(1 * base))
  const workerPods = Math.max(2, Math.round(2 * base))
  const totalPods = backendPods + frontendPods + workerPods
  const cpuCores = totalPods * 2
  const memoryGB = totalPods * 4
  const storageTB = Math.max(0.1, Math.round((totalPods * 0.05) * 10) / 10)

  let redisType: string, redisMem: string, redisNodes: number
  if (loadFactor < 0.5) {
    redisType = "cache.t3.small"; redisMem = "1 GB"; redisNodes = 1
  } else if (loadFactor < 1) {
    redisType = "cache.m6g.large"; redisMem = "6 GB"; redisNodes = 2
  } else if (loadFactor < 3) {
    redisType = "cache.m6g.xlarge"; redisMem = "13 GB"; redisNodes = 3
  } else {
    redisType = "cache.m6g.2xlarge"; redisMem = "25 GB"; redisNodes = 4
  }

  let neo4jType: string, neo4jMem: string, neo4jNodes: number
  if (loadFactor < 0.5) {
    neo4jType = "db.t3.medium"; neo4jMem = "4 GB"; neo4jNodes = 1
  } else if (loadFactor < 1) {
    neo4jType = "db.r5.large"; neo4jMem = "16 GB"; neo4jNodes = 1
  } else if (loadFactor < 3) {
    neo4jType = "db.r5.xlarge"; neo4jMem = "32 GB"; neo4jNodes = 2
  } else {
    neo4jType = "db.r5.2xlarge"; neo4jMem = "64 GB"; neo4jNodes = 3
  }

  const computeCost = cpuCores * 35
  const memCost = memoryGB * 8
  const storCost = storageTB * 120
  const dbCost = (redisNodes * 85 + neo4jNodes * 350)
  const netCost = totalPods * 15
  const totalMonthly = computeCost + memCost + storCost + dbCost + netCost

  return {
    backendPods, frontendPods, workerPods, totalPods,
    cpuCores, memoryGB, storageTB,
    redisType, redisMem, redisNodes,
    neo4jType, neo4jMem, neo4jNodes,
    monthlyCost: `$${totalMonthly.toLocaleString()}`,
    costBreakdown: { compute: computeCost, memory: memCost, storage: storCost, database: dbCost, network: netCost },
  }
}

const maxCostTotal = 40000

export default function ScalingSimulatorPanel() {
  const [users, setUsers] = useState(1000)
  const [missionsPerHour, setMissionsPerHour] = useState(100)
  const [workers, setWorkers] = useState(10)
  const [avgDuration, setAvgDuration] = useState(15)
  const [result, setResult] = useState<ScalingResult | null>(null)

  const simulate = () => {
    setResult(calculateScaling(users, missionsPerHour, workers, avgDuration))
  }

  return (
    <div className="space-y-6">
      <SectionHeader title="Scaling Simulator" subtitle="Estimate infrastructure needs based on expected load" />

      <div className="grid grid-cols-2 gap-6">
        <div className="bg-white rounded-[18px] border border-[#E8EDF3] p-5 shadow-sm">
          <SectionHeader title="Configuration" />

          <div className="space-y-5">
            <div>
              <label className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1.5 block">
                Expected Users: {users.toLocaleString()}
              </label>
              <input type="range" min={100} max={100000} value={users} onChange={(e) => setUsers(Number(e.target.value))}
                className="w-full h-2 bg-gray-100 rounded-full appearance-none cursor-pointer accent-[#38B88A]" />
              <div className="flex justify-between text-xs text-gray-400 mt-0.5"><span>100</span><span>100,000</span></div>
            </div>
            <div>
              <label className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1.5 block">
                Missions/Hour: {missionsPerHour.toLocaleString()}
              </label>
              <input type="range" min={10} max={10000} value={missionsPerHour} onChange={(e) => setMissionsPerHour(Number(e.target.value))}
                className="w-full h-2 bg-gray-100 rounded-full appearance-none cursor-pointer accent-[#38B88A]" />
              <div className="flex justify-between text-xs text-gray-400 mt-0.5"><span>10</span><span>10,000</span></div>
            </div>
            <div>
              <label className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1.5 block">
                Workers Needed: {workers}
              </label>
              <input type="range" min={1} max={500} value={workers} onChange={(e) => setWorkers(Number(e.target.value))}
                className="w-full h-2 bg-gray-100 rounded-full appearance-none cursor-pointer accent-[#38B88A]" />
              <div className="flex justify-between text-xs text-gray-400 mt-0.5"><span>1</span><span>500</span></div>
            </div>
            <div>
              <label className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1.5 block">
                Avg Mission Duration: {avgDuration} min
              </label>
              <input type="range" min={1} max={60} value={avgDuration} onChange={(e) => setAvgDuration(Number(e.target.value))}
                className="w-full h-2 bg-gray-100 rounded-full appearance-none cursor-pointer accent-[#38B88A]" />
              <div className="flex justify-between text-xs text-gray-400 mt-0.5"><span>1 min</span><span>60 min</span></div>
            </div>

            <button
              onClick={simulate}
              className="w-full py-2.5 bg-[#38B88A] hover:bg-emerald-600 text-white text-sm font-semibold rounded-xl transition-colors flex items-center justify-center gap-2"
            >
              <Play size={16} /> Simulate Scaling
            </button>
          </div>
        </div>

        <div className="space-y-4">
          {result ? (
            <>
              <div className="bg-white rounded-[18px] border border-[#E8EDF3] p-5 shadow-sm">
                <SectionHeader title="Estimated Infrastructure" />
                <div className="grid grid-cols-2 gap-3">
                  <KpiCard title="Backend Pods" value={String(result.backendPods)} icon={<Server size={16} />} />
                  <KpiCard title="Frontend Pods" value={String(result.frontendPods)} icon={<Server size={16} />} />
                  <KpiCard title="Worker Pods" value={String(result.workerPods)} icon={<Cpu size={16} />} />
                  <KpiCard title="Total Pods" value={String(result.totalPods)} icon={<Server size={16} />} />
                </div>
              </div>

              <div className="bg-white rounded-[18px] border border-[#E8EDF3] p-5 shadow-sm">
                <div className="space-y-2">
                  <MetricRow label="CPU Required" value={`${result.cpuCores} cores`} icon={<Cpu size={14} />} />
                  <MetricRow label="Memory Required" value={`${result.memoryGB} GB`} icon={<HardDrive size={14} />} />
                  <MetricRow label="Storage Required" value={`${result.storageTB} TB`} icon={<Database size={14} />} />
                  <MetricRow label="Redis" value={`${result.redisType} · ${result.redisMem} · ${result.redisNodes} nodes`} icon={<Database size={14} />} />
                  <MetricRow label="Neo4j" value={`${result.neo4jType} · ${result.neo4jMem} · ${result.neo4jNodes} nodes`} icon={<Database size={14} />} />
                  <MetricRow label="Estimated Monthly Cost" value={result.monthlyCost} color="#38B88A" icon={<DollarSign size={14} />} />
                </div>
              </div>

              <div className="bg-white rounded-[18px] border border-[#E8EDF3] p-5 shadow-sm">
                <SectionHeader title="Cost Breakdown by Category" />
                <div className="space-y-2">
                  {Object.entries(result.costBreakdown).map(([key, val]) => {
                    const colorMap: Record<string, string> = { compute: "#3B82F6", memory: "#8B5CF6", storage: "#F59E0B", database: "#38B88A", network: "#EF4444" }
                    return (
                      <ProgressBar
                        key={key}
                        label={key.charAt(0).toUpperCase() + key.slice(1)}
                        value={val}
                        max={maxCostTotal}
                        color={colorMap[key] || "#38B88A"}
                        size="md"
                      />
                    )
                  })}
                </div>
              </div>
            </>
          ) : (
            <div className="bg-white rounded-[18px] border border-[#E8EDF3] p-8 shadow-sm flex items-center justify-center h-full">
              <div className="text-center max-w-sm">
                <BarChart3 size={40} className="text-gray-300 mx-auto mb-3" />
                <h4 className="text-base font-semibold text-gray-700 mb-1">Ready to Simulate</h4>
                <p className="text-xs text-gray-400">Configure your expected load and click "Simulate Scaling" to estimate infrastructure requirements.</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function MetricRow({ label, value, icon, color }: { label: string; value: string; icon?: React.ReactNode; color?: string }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-[#E8EDF3] last:border-0">
      <div className="flex items-center gap-2">
        {icon && <span className="text-gray-400">{icon}</span>}
        <span className="text-sm text-gray-600">{label}</span>
      </div>
      <span className="text-sm font-semibold text-gray-900" style={color ? { color } : undefined}>{value}</span>
    </div>
  )
}