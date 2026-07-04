"use client"

import { useState } from "react"
import { Play, RotateCcw, AlertTriangle, CheckCircle2, Clock } from "lucide-react"

const STAGES = ["INIT", "PLANNING", "RESEARCHING", "REASONING", "VALIDATING", "GENERATING", "MEMORY_UPDATE", "COMPLETED"]

export default function MissionControl() {
  const [selectedMission, setSelectedMission] = useState<string | null>(null)
  const missions = [
    { id: "mis_001", name: "Software Release v3.0", status: "running", stage: "VALIDATING", confidence: 0.92, workers: ["planner", "research", "critic"] },
    { id: "mis_002", name: "Security Investigation", status: "pending", stage: "INIT", confidence: 0, workers: ["browser"] },
    { id: "mis_003", name: "Executive Research", status: "completed", stage: "COMPLETED", confidence: 0.95, workers: ["planner", "research"] },
  ]

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Mission Control</h1>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-1 border border-white/5 rounded-xl p-4 bg-white/[0.02]">
          <h2 className="text-sm font-medium text-white/60 mb-3">Active Missions</h2>
          <div className="space-y-2">
            {missions.map((m) => (
              <button
                key={m.id}
                onClick={() => setSelectedMission(m.id)}
                className={`w-full text-left p-3 rounded-lg border transition-all ${
                  selectedMission === m.id
                    ? "border-emerald-500/30 bg-emerald-500/5"
                    : "border-white/5 hover:border-white/10"
                }`}
              >
                <div className="text-sm font-medium text-white/80">{m.name}</div>
                <div className="flex items-center gap-2 mt-1">
                  {m.status === "running" && <Play className="w-3 h-3 text-emerald-400" />}
                  {m.status === "completed" && <CheckCircle2 className="w-3 h-3 text-blue-400" />}
                  {m.status === "pending" && <Clock className="w-3 h-3 text-white/30" />}
                  <span className="text-xs text-white/40">{m.stage}</span>
                  {m.confidence > 0 && <span className="text-xs text-white/30">· {(m.confidence * 100).toFixed(0)}%</span>}
                </div>
              </button>
            ))}
          </div>
        </div>

        <div className="lg:col-span-2 border border-white/5 rounded-xl p-4 bg-white/[0.02]">
          <h2 className="text-sm font-medium text-white/60 mb-4">Execution Pipeline</h2>
          {selectedMission ? (
            <div className="space-y-4">
              <div className="flex items-center gap-1.5 flex-wrap">
                {STAGES.map((stage, i) => {
                  const mission = missions.find((m) => m.id === selectedMission)
                  const currentIdx = STAGES.indexOf(mission?.stage || "INIT")
                  const completed = i < currentIdx
                  const active = i === currentIdx
                  return (
                    <div key={stage} className="flex items-center gap-1.5">
                      <div className={`px-2.5 py-1 rounded-md text-[11px] font-medium border transition-all ${
                        active ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400" :
                        completed ? "bg-white/5 border-white/10 text-white/50" :
                        "border-white/5 text-white/20"
                      }`}>{stage}</div>
                      {i < STAGES.length - 1 && <div className="w-3 h-px bg-white/10" />}
                    </div>
                  )
                })}
              </div>
              <div className="p-4 rounded-lg border border-white/5 bg-white/[0.01]">
                <div className="text-sm text-white/60">Select a mission to view detailed execution logs, worker assignments, and progress.</div>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-32 text-sm text-white/30">
              Select a mission to view execution details
            </div>
          )}
        </div>
      </div>
    </div>
  )
}