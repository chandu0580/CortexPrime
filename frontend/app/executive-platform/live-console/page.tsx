"use client"

import { Terminal, Radio, Activity } from "lucide-react"

export default function LiveAgentConsole() {
  const workers = [
    { name: "Browser Worker", status: "idle", icon: Radio, latency: "—", health: "healthy" },
    { name: "Voice Worker", status: "idle", icon: Radio, latency: "—", health: "healthy" },
    { name: "Reasoning Runtime", status: "active", icon: Activity, latency: "1.2s", health: "healthy" },
    { name: "Mission Runtime", status: "active", icon: Terminal, latency: "0.4s", health: "healthy" },
  ]

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Live Agent Console</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {workers.map((w) => (
          <div key={w.name} className="border border-white/5 rounded-xl p-4 bg-white/[0.02]">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <w.icon className="w-4 h-4 text-emerald-400" />
                <span className="text-sm font-medium">{w.name}</span>
              </div>
              <span className={`text-xs px-2 py-0.5 rounded-full border ${
                w.status === "active" ? "text-emerald-400 border-emerald-500/20 bg-emerald-500/5" : "text-white/30 border-white/10"
              }`}>{w.status}</span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div><span className="text-white/30">Latency</span><br /><span className="text-white/60">{w.latency}</span></div>
              <div><span className="text-white/30">Health</span><br /><span className="text-emerald-400">{w.health}</span></div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}