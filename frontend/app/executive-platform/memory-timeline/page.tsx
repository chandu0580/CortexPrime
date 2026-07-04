"use client"

import { History, Brain, BookOpen, Lightbulb } from "lucide-react"

const MEMORY_TYPES = [
  { type: "Episodic", icon: History, color: "text-blue-400", count: 128 },
  { type: "Semantic", icon: Brain, color: "text-violet-400", count: 64 },
  { type: "Working", icon: BookOpen, color: "text-emerald-400", count: 12 },
  { type: "Reflection", icon: Lightbulb, color: "text-amber-400", count: 32 },
]

const TIMELINE = [
  { time: "2m ago", event: "Mission completed: Knowledge Discovery", type: "mission", agent: "research" },
  { time: "5m ago", event: "Memory retrieved: BrowserWorker session data", type: "memory", agent: "memory" },
  { time: "12m ago", event: "Reflection generated for mission mis_003", type: "reflection", agent: "critic" },
  { time: "25m ago", event: "Semantic fact stored: Project configuration", type: "memory", agent: "memory" },
  { time: "1h ago", event: "Mission planned: Executive Research v2", type: "mission", agent: "planner" },
]

export default function MemoryTimeline() {
  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Memory Timeline</h1>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {MEMORY_TYPES.map((mt) => (
          <div key={mt.type} className="border border-white/5 rounded-xl p-4 bg-white/[0.02]">
            <div className="flex items-center gap-2 mb-2">
              <mt.icon className={`w-4 h-4 ${mt.color}`} />
              <span className="text-xs text-white/40">{mt.type}</span>
            </div>
            <div className={`text-xl font-semibold ${mt.color}`}>{mt.count}</div>
          </div>
        ))}
      </div>

      <div className="border border-white/5 rounded-xl p-4 bg-white/[0.02]">
        <h2 className="text-sm font-medium text-white/60 mb-3">Recent Activity</h2>
        <div className="space-y-1">
          {TIMELINE.map((item, i) => (
            <div key={i} className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/[0.02] text-sm">
              <span className="text-[10px] text-white/20 w-12 shrink-0">{item.time}</span>
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-400/50 shrink-0" />
              <span className="text-white/60">{item.event}</span>
              <span className="text-[10px] text-white/20 ml-auto">{item.agent}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}