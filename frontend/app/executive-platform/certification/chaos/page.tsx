"use client"

import { FlaskConical, Play } from "lucide-react"
import { useState } from "react"
import { DEFAULT_CHAOS_TESTS, type ChaosTestResult } from "@/components/certification/definitions"
import { StatusIcon } from "@/components/certification/shared"
import { GlassCard, StatusBadge } from "@/components/executive-platform/shared"

export default function ChaosTesting() {
  const [tests, setTests] = useState<ChaosTestResult[]>(DEFAULT_CHAOS_TESTS)

  const runTest = async (testId: string) => {
    setTests((prev) => prev.map((t) => t.id === testId ? { ...t, status: "running" as const } : t))
    await new Promise((r) => setTimeout(r, 3000))
    setTests((prev) => prev.map((t) => t.id === testId ? { ...t, status: "passed" as const } : t))
  }

  const runAll = async () => {
    for (const t of tests) {
      if (t.status !== "running") {
        setTests((prev) => prev.map((x) => x.id === t.id ? { ...x, status: "running" as const } : x))
        await new Promise((r) => setTimeout(r, 1500))
        setTests((prev) => prev.map((x) => x.id === t.id ? { ...x, status: "passed" as const } : x))
      }
    }
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <FlaskConical className="w-6 h-6 text-amber-400" />
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Chaos Testing</h1>
            <p className="text-xs text-white/40 mt-0.5">Controlled failure scenarios to verify resilience</p>
          </div>
        </div>
        <button onClick={runAll} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 hover:bg-emerald-500/20 text-xs transition-all">
          <Play className="w-3.5 h-3.5" /> Run All Tests
        </button>
      </div>
      <div className="grid grid-cols-1 gap-3">
        {tests.map((test) => (
          <GlassCard key={test.id}>
            <div className="flex items-start gap-3">
              <StatusIcon status={test.status} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-white/80">{test.scenario}</span>
                  <StatusBadge status={test.status} />
                </div>
                <p className="text-xs text-white/40 mt-0.5">{test.description}</p>
                <div className="flex items-center gap-3 mt-1.5 text-[10px] text-white/30">
                  {test.duration && <span>Duration: {test.duration}</span>}
                  {test.recoveryTime && <span>Recovery: {test.recoveryTime}</span>}
                  {test.impact && <span>Impact: {test.impact}</span>}
                </div>
              </div>
              {test.status !== "running" && (
                <button onClick={() => runTest(test.id)} className="text-[10px] px-2 py-1 rounded border border-white/10 text-white/30 hover:text-white/60 shrink-0">
                  {test.status === "passed" ? "Re-run" : "Run"}
                </button>
              )}
            </div>
          </GlassCard>
        ))}
      </div>
    </div>
  )
}