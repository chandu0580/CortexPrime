"use client"

import { Activity, Radio, BarChart3, RefreshCw } from "lucide-react"

export default function ObservabilityCenter() {
  const traces = [
    { id: "tr_001", service: "MissionRuntime", duration: "1.2s", status: "ok", timestamp: "2s ago" },
    { id: "tr_002", service: "LLMRouter", duration: "0.8s", status: "ok", timestamp: "2s ago" },
    { id: "tr_003", service: "MemoryRetrieval", duration: "0.3s", status: "ok", timestamp: "3s ago" },
    { id: "tr_004", service: "Neo4jQuery", duration: "0.15s", status: "ok", timestamp: "3s ago" },
    { id: "tr_005", service: "BrowserAgent", duration: "—", status: "idle", timestamp: "30s ago" },
  ]

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Observability</h1>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 border border-white/5 rounded-xl p-4 bg-white/[0.02]">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-medium text-white/60">Live Traces</h2>
            <RefreshCw className="w-3.5 h-3.5 text-white/20" />
          </div>
          <div className="space-y-1">
            {traces.map((t) => (
              <div key={t.id} className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/[0.02] text-sm">
                <div className={`w-1.5 h-1.5 rounded-full ${t.status === "ok" ? "bg-emerald-400" : "bg-white/20"}`} />
                <span className="text-white/60 w-32">{t.service}</span>
                <span className="text-white/30 text-xs">{t.duration}</span>
                <span className="text-[10px] text-white/20 ml-auto">{t.timestamp}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="border border-white/5 rounded-xl p-4 bg-white/[0.02]">
          <h2 className="text-sm font-medium text-white/60 mb-3">Runtime Health</h2>
          <div className="space-y-3">
            {[
              { label: "Up Time", value: "12h 34m", color: "text-emerald-400" },
              { label: "Events/min", value: "47", color: "text-blue-400" },
              { label: "Error Rate", value: "0.02%", color: "text-emerald-400" },
              { label: "Throughput", value: "28 req/s", color: "text-violet-400" },
            ].map((m) => (
              <div key={m.label} className="flex items-center justify-between text-sm">
                <span className="text-white/40">{m.label}</span>
                <span className={m.color}>{m.value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}