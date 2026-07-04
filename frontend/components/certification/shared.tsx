"use client"

import { GlassCard, StatusBadge } from "@/components/executive-platform/shared"
import { CheckCircle2, XCircle, AlertTriangle, Loader2 } from "lucide-react"

export function CertificationScoreCard({ label, score, maxScore, status, checks, passed }: {
  label: string; score: number; maxScore: number; status: string; checks: number; passed: number
}) {
  const pct = Math.round((score / maxScore) * 100)
  return (
    <GlassCard>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-white/60 font-medium">{label}</span>
        <StatusBadge status={status} />
      </div>
      <div className="flex items-baseline gap-1 mb-2">
        <span className={`text-2xl font-semibold ${status === "passed" ? "text-emerald-400" : status === "warning" ? "text-amber-400" : "text-red-400"}`}>{pct}%</span>
        <span className="text-xs text-white/30">({score}/{maxScore})</span>
      </div>
      <div className="w-full h-1.5 bg-white/5 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all ${
          status === "passed" ? "bg-emerald-400" : status === "warning" ? "bg-amber-400" : "bg-red-400"
        }`} style={{ width: `${pct}%` }} />
      </div>
      <div className="text-[10px] text-white/30 mt-1.5">{passed}/{checks} checks passed</div>
    </GlassCard>
  )
}

export function CertificationBadge({ status }: { status: "certified" | "failed" | "pending" }) {
  if (status === "certified") return <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-medium">Certified</span>
  if (status === "failed") return <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-500/10 border border-red-500/20 text-red-400 font-medium">Failed</span>
  return <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-400 font-medium">Pending</span>
}

export function StatusIcon({ status }: { status: string }) {
  if (status === "healthy" || status === "passed" || status === "good" || status === "certified") return <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
  if (status === "degraded" || status === "warning" || status === "acceptable" || status === "pending") return <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
  if (status === "unhealthy" || status === "failed" || status === "poor") return <XCircle className="w-4 h-4 text-red-400 shrink-0" />
  if (status === "running") return <Loader2 className="w-4 h-4 text-blue-400 animate-spin shrink-0" />
  return <div className="w-4 h-4 rounded-full bg-white/20 shrink-0" />
}

export function OverallScoreRing({ score, label }: { score: number; label: string }) {
  const radius = 36
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (score / 100) * circumference
  const color = score >= 90 ? "stroke-emerald-400" : score >= 75 ? "stroke-amber-400" : "stroke-red-400"
  return (
    <div className="flex flex-col items-center">
      <svg width="100" height="100" className="-rotate-90">
        <circle cx="50" cy="50" r={radius} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="8" />
        <circle cx="50" cy="50" r={radius} fill="none" className={color} strokeWidth="8" strokeDasharray={circumference} strokeDashoffset={offset} strokeLinecap="round" />
      </svg>
      <div className="text-2xl font-semibold -mt-16 text-white/90">{score}%</div>
      <div className="text-[10px] text-white/40 mt-1">{label}</div>
    </div>
  )
}