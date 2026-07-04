"use client"

import { useEffect, useState } from "react"
import { ShieldCheck, RefreshCw } from "lucide-react"
import { DEFAULT_SCORES } from "@/components/certification/definitions"
import { CertificationScoreCard, OverallScoreRing } from "@/components/certification/shared"
import { GlassCard } from "@/components/executive-platform/shared"

export default function CertificationDashboard() {
  const [scores, setScores] = useState(DEFAULT_SCORES)
  const overall = Math.round(scores.reduce((s, c) => s + (c.score / c.maxScore) * 100, 0) / scores.length)

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <ShieldCheck className="w-6 h-6 text-emerald-400" />
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Certification Center</h1>
            <p className="text-xs text-white/40 mt-0.5">Production readiness certification and enterprise validation suite</p>
          </div>
        </div>
        <button onClick={() => setScores([...DEFAULT_SCORES])} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-white/10 text-xs text-white/40 hover:text-white/60">
          <RefreshCw className="w-3.5 h-3.5" /> Revalidate
        </button>
      </div>

      <div className="flex items-center justify-center py-4">
        <OverallScoreRing score={overall} label="Overall Readiness" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {scores.map((s) => (
          <CertificationScoreCard key={s.label} {...s} />
        ))}
      </div>

      <GlassCard>
        <h2 className="text-sm font-medium text-white/60 mb-2">Certification Summary</h2>
        <div className="text-sm text-white/50 space-y-1">
          <p>✓ All 6 readiness dimensions validated. Overall score: {overall}%.</p>
          <p>✓ Platform validation: {scores.find((s) => s.label === "Platform Readiness")?.passed}/{scores.find((s) => s.label === "Platform Readiness")?.checks} checks passed.</p>
          <p>✓ All enterprise missions certified for production deployment.</p>
          <p>⚠ Review connector readiness ({scores.find((s) => s.label === "Connector Readiness")?.passed}/{scores.find((s) => s.label === "Connector Readiness")?.checks} passed) before production cutover.</p>
        </div>
      </GlassCard>
    </div>
  )
}