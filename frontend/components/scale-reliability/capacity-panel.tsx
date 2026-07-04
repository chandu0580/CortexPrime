"use client"

import { useState } from "react"
import {
  Users,
  Server,
  Cpu,
  HardDrive,
  Database,
  DollarSign,
  BarChart3,
  ArrowLeft,
  ArrowRight,
} from "lucide-react"
import { KpiCard, SectionHeader, DataTable } from "./shared"

const tiers = [100, 500, 1000, 5000, 10000]

const infraData: Record<number, Record<string, string | string[]>> = {
  100: {
    backendPods: "2", frontendPods: "1", workerPods: "2",
    backendCPU: "4", frontendCPU: "2", workerCPU: "4",
    backendMem: "8", frontendMem: "4", workerMem: "8",
    redisType: "cache.t3.micro", redisMem: "0.5 GB", redisNodes: "1",
    neo4jType: "db.t3.medium", neo4jMem: "4 GB", neo4jNodes: "1",
    pgType: "db.t3.small", pgStorage: "20 GB", pgReplicas: "1",
    monthlyCost: "$1,240",
  },
  500: {
    backendPods: "4", frontendPods: "2", workerPods: "4",
    backendCPU: "8", frontendCPU: "4", workerCPU: "8",
    backendMem: "16", frontendMem: "8", workerMem: "16",
    redisType: "cache.t3.small", redisMem: "1 GB", redisNodes: "2",
    neo4jType: "db.r5.large", neo4jMem: "16 GB", neo4jNodes: "2",
    pgType: "db.r5.large", pgStorage: "100 GB", pgReplicas: "2",
    monthlyCost: "$4,850",
  },
  1000: {
    backendPods: "8", frontendPods: "3", workerPods: "8",
    backendCPU: "16", frontendCPU: "6", workerCPU: "16",
    backendMem: "32", frontendMem: "12", workerMem: "32",
    redisType: "cache.m6g.large", redisMem: "6 GB", redisNodes: "3",
    neo4jType: "db.r5.xlarge", neo4jMem: "32 GB", neo4jNodes: "2",
    pgType: "db.r5.xlarge", pgStorage: "250 GB", pgReplicas: "2",
    monthlyCost: "$9,200",
  },
  5000: {
    backendPods: "16", frontendPods: "6", workerPods: "16",
    backendCPU: "32", frontendCPU: "12", workerCPU: "32",
    backendMem: "64", frontendMem: "24", workerMem: "64",
    redisType: "cache.m6g.xlarge", redisMem: "13 GB", redisNodes: "4",
    neo4jType: "db.r5.2xlarge", neo4jMem: "64 GB", neo4jNodes: "3",
    pgType: "db.r5.2xlarge", pgStorage: "500 GB", pgReplicas: "3",
    monthlyCost: "$24,500",
  },
  10000: {
    backendPods: "32", frontendPods: "12", workerPods: "32",
    backendCPU: "64", frontendCPU: "24", workerCPU: "64",
    backendMem: "128", frontendMem: "48", workerMem: "128",
    redisType: "cache.m6g.2xlarge", redisMem: "25 GB", redisNodes: "6",
    neo4jType: "db.r5.4xlarge", neo4jMem: "128 GB", neo4jNodes: "4",
    pgType: "db.r5.4xlarge", pgStorage: "1,000 GB", pgReplicas: "3",
    monthlyCost: "$52,800",
  },
}

const costData = tiers.map((t) => ({
  tier: `${t.toLocaleString()} users`,
  cost: Number(String(infraData[t].monthlyCost).replace(/[$,]/g, "")),
}))

const maxCost = Math.max(...costData.map((c) => c.cost))

export default function CapacityPanel() {
  const [selectedTier, setSelectedTier] = useState(1000)

  const infra = infraData[selectedTier]

  const columns = [
    { key: "category", label: "Category" },
    { key: "spec", label: "Specification" },
    { key: "detail", label: "Detail" },
  ]

  const infraRows = [
    { category: "Backend Pods", spec: `${infra.backendPods} pods`, detail: `${infra.backendCPU} CPU cores, ${infra.backendMem} GB RAM` },
    { category: "Frontend Pods", spec: `${infra.frontendPods} pods`, detail: `${infra.frontendCPU} CPU cores, ${infra.frontendMem} GB RAM` },
    { category: "Worker Pods", spec: `${infra.workerPods} pods`, detail: `${infra.workerCPU} CPU cores, ${infra.workerMem} GB RAM` },
    { category: "Redis", spec: `${infra.redisType}`, detail: `${infra.redisMem}, ${infra.redisNodes} nodes` },
    { category: "Neo4j", spec: `${infra.neo4jType}`, detail: `${infra.neo4jMem}, ${infra.neo4jNodes} nodes` },
    { category: "PostgreSQL", spec: `${infra.pgType}`, detail: `${infra.pgStorage} storage, ${infra.pgReplicas} replicas` },
    { category: "Monthly Cost", spec: `${infra.monthlyCost}`, detail: "Estimated AWS on-demand pricing" },
  ]

  return (
    <div className="space-y-6">
      <SectionHeader title="Capacity Planning" subtitle="Estimate infrastructure requirements for different user tiers" />

      <div className="bg-white rounded-[18px] border border-[#E8EDF3] p-5 shadow-sm">
        <div className="flex items-center gap-2 mb-6">
          <Users size={16} className="text-gray-400" />
          <span className="text-sm font-medium text-gray-700">Select User Tier:</span>
          <div className="flex gap-2 ml-2">
            {tiers.map((t) => (
              <button
                key={t}
                onClick={() => setSelectedTier(t)}
                className={`px-5 py-2 text-sm font-semibold rounded-xl border transition-all ${
                  selectedTier === t
                    ? "border-[#38B88A] bg-[#38B88A] text-white shadow-md"
                    : "border-[#E8EDF3] text-gray-600 hover:border-gray-300 bg-white"
                }`}
              >
                {t.toLocaleString()}
              </button>
            ))}
          </div>
        </div>

        <div className="p-4 rounded-xl bg-gradient-to-r from-emerald-50 to-emerald-100/50 border border-emerald-200 mb-6">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-xs font-medium text-emerald-700 uppercase tracking-wide">Active Tier</span>
              <h2 className="text-2xl font-bold text-gray-900 mt-0.5">{selectedTier.toLocaleString()} Users</h2>
            </div>
            <div className="text-right">
              <span className="text-xs font-medium text-emerald-700 uppercase tracking-wide">Estimated Monthly Cost</span>
              <p className="text-xl font-bold text-[#38B88A]">{infra.monthlyCost}</p>
            </div>
          </div>
        </div>

        <SectionHeader title="Infrastructure Requirements" />
        <DataTable columns={columns} rows={infraRows} />
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="bg-white rounded-[18px] border border-[#E8EDF3] p-5 shadow-sm">
          <SectionHeader title="Cost Comparison" subtitle="Monthly cost across all tiers" />
          <div className="space-y-3 mt-4">
            {costData.map((c) => {
              const pct = (c.cost / maxCost) * 100
              return (
                <div key={c.tier}>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-gray-600">{c.tier}</span>
                    <span className="text-gray-900 font-medium">${c.cost.toLocaleString()}</span>
                  </div>
                  <div className="w-full h-3 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{ width: `${pct}%`, backgroundColor: selectedTier === Number(c.tier.split(" ")[0].replace(/,/g, "")) ? "#38B88A" : "#d1d5db" }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        <div className="bg-white rounded-[18px] border border-[#E8EDF3] p-5 shadow-sm">
          <SectionHeader title="Cost Projection" subtitle="Estimated monthly cost by tier" />
          <div className="flex items-end gap-3 h-48 pt-4">
            {costData.map((c) => {
              const pct = (c.cost / maxCost) * 100
              return (
                <div key={c.tier} className="flex-1 flex flex-col items-center gap-1.5 h-full justify-end">
                  <span className="text-[10px] text-gray-500 font-medium">${(c.cost / 1000).toFixed(0)}k</span>
                  <div
                    className="w-full rounded-lg transition-all duration-500 cursor-pointer hover:opacity-80"
                    style={{
                      height: `${pct}%`,
                      backgroundColor: selectedTier === Number(c.tier.split(" ")[0].replace(/,/g, "")) ? "#38B88A" : "#d1d5db",
                    }}
                  />
                  <span className="text-[9px] text-gray-400 text-center leading-tight">{c.tier}</span>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}