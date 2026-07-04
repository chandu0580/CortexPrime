"use client"

import { useState } from "react"
import { FileText, Download, CheckCircle2, AlertTriangle } from "lucide-react"
import { DEFAULT_SCORES, DEFAULT_BENCHMARKS, DEFAULT_CHAOS_TESTS, DEFAULT_SECURITY_ITEMS, DEFAULT_MISSION_CERTIFICATIONS } from "@/components/certification/definitions"
import { GlassCard } from "@/components/executive-platform/shared"

export default function CertificationReports() {
  const [format, setFormat] = useState<"markdown" | "json">("markdown")
  const scores = DEFAULT_SCORES
  const overall = Math.round(scores.reduce((s, c) => s + (c.score / c.maxScore) * 100, 0) / scores.length)

  const reportMD = `# CortexPrime Certification Report
## Generated: ${new Date().toISOString()}

### Overall Score: ${overall}%

| Dimension | Score | Status |
|-----------|-------|--------|
${scores.map((s) => `| ${s.label} | ${s.score}/${s.maxScore} (${Math.round((s.score/s.maxScore)*100)}%) | ${s.status} |`).join("\n")}

### Performance Benchmarks
| Benchmark | Value | p50 | p95 | p99 |
|-----------|-------|-----|-----|-----|
${DEFAULT_BENCHMARKS.map((b) => `| ${b.name} | ${b.value} | ${b.p50} | ${b.p95} | ${b.p99} |`).join("\n")}

### Chaos Tests
${DEFAULT_CHAOS_TESTS.map((t) => `- ${t.scenario}: ${t.status} (recovery: ${t.recoveryTime})`).join("\n")}

### Security Validation
${DEFAULT_SECURITY_ITEMS.map((s) => `- ${s.name}: ${s.status}`).join("\n")}

### Mission Certification
${DEFAULT_MISSION_CERTIFICATIONS.map((m) => `- ${m.name}: ${m.status}`).join("\n")}

### Summary
- Platform Readiness: ${scores.find((s) => s.label === "Platform Readiness")?.score}%
- Security Readiness: ${scores.find((s) => s.label === "Security Readiness")?.score}%
- Deployment Readiness: ${scores.find((s) => s.label === "Deployment Readiness")?.score}%
- Overall: ${overall}%
`

  const reportJSON = JSON.stringify({
    generatedAt: new Date().toISOString(),
    overallScore: overall,
    dimensions: scores,
    benchmarks: DEFAULT_BENCHMARKS,
    chaosTests: DEFAULT_CHAOS_TESTS,
    security: DEFAULT_SECURITY_ITEMS,
    missions: DEFAULT_MISSION_CERTIFICATIONS,
  }, null, 2)

  const download = () => {
    const content = format === "markdown" ? reportMD : reportJSON
    const ext = format === "markdown" ? "md" : "json"
    const blob = new Blob([content], { type: "text/plain" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url; a.download = `cortexprime-certification.${ext}`; a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <FileText className="w-6 h-6 text-emerald-400" />
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Certification Reports</h1>
            <p className="text-xs text-white/40 mt-0.5">Export certification results in MD or JSON</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex rounded-lg border border-white/10 overflow-hidden">
            <button onClick={() => setFormat("markdown")} className={`px-3 py-1.5 text-xs transition-all ${format === "markdown" ? "bg-white/10 text-white" : "text-white/30 hover:text-white/60"}`}>MD</button>
            <button onClick={() => setFormat("json")} className={`px-3 py-1.5 text-xs transition-all ${format === "json" ? "bg-white/10 text-white" : "text-white/30 hover:text-white/60"}`}>JSON</button>
          </div>
          <button onClick={download} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-white/10 text-xs text-white/40 hover:text-white/60">
            <Download className="w-3.5 h-3.5" /> Export
          </button>
        </div>
      </div>

      <GlassCard>
        <pre className="text-xs text-white/60 font-mono whitespace-pre-wrap leading-relaxed max-h-[70vh] overflow-y-auto">
          {format === "markdown" ? reportMD : reportJSON}
        </pre>
      </GlassCard>
    </div>
  )
}