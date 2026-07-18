"use client"

import { useState } from "react"
import {
  FileText,
  Download,
  Mail,
  Calendar,
  Clock,
  CheckCircle2,
  AlertTriangle,
  HelpCircle,
  ArrowUpRight,
  Settings,
} from "lucide-react"
import { StatusBadge, KpiCard, SectionHeader, DataTable } from "./shared"

const formats = ["Markdown", "JSON", "PDF"] as const
type ReportFormat = (typeof formats)[number]

const kpiHighlights = [
  { label: "Current Scale", value: "1,000 users", detail: "Active user tier" },
  { label: "Headroom", value: "67%", detail: "Available capacity before next tier" },
  { label: "Recommended", value: "5,000 users", detail: "Next tier with 85% utilization" },
]

const scalingRecs = [
  { component: "Backend Pods", current: "8", recommended: "16", reason: "Expected 3× growth" },
  { component: "Redis Nodes", current: "3", recommended: "4", reason: "Read replica for HA" },
  { component: "Neo4j Nodes", current: "2", recommended: "3", reason: "Write contention at 1,800 TPS" },
  { component: "PG Replicas", current: "2", recommended: "3", reason: "Read scaling for analytics" },
]

const costEstimates = [
  { tier: "Current (1,000 users)", cost: "$9,200/mo", breakdown: "Compute: $3,800 · Storage: $1,200 · Database: $4,200" },
  { tier: "Next (5,000 users)", cost: "$24,500/mo", breakdown: "Compute: $10,200 · Storage: $3,500 · Database: $10,800" },
  { tier: "Future (10,000 users)", cost: "$52,800/mo", breakdown: "Compute: $22,000 · Storage: $7,500 · Database: $23,300" },
]

const riskItems = [
  { item: "Neo4j write contention at high TPS", level: "High", mitigation: "Scale to 3 nodes before reaching tier" },
  { item: "LLM rate limiting at 2,100 TPS", level: "Medium", mitigation: "Increase rate limits; add fallback providers" },
  { item: "Redis connection pool limits", level: "Medium", mitigation: "Increase pool size or add read replicas" },
  { item: "PostgreSQL connection pool exhaustion", level: "Low", mitigation: "Increase pool to 50; enable connection pooling" },
  { item: "Memory under-provisioning at peak", level: "Low", mitigation: "Current headroom sufficient for projected growth" },
]

const actionItems = [
  { priority: "High", action: "Scale Neo4j to 3 nodes", owner: "Infrastructure Team", deadline: "Q3 2026" },
  { priority: "High", action: "Implement LLM fallback providers", owner: "Platform Team", deadline: "Q3 2026" },
  { priority: "Medium", action: "Increase Redis pool to 6 nodes", owner: "SRE Team", deadline: "Q4 2026" },
  { priority: "Medium", action: "Enable PostgreSQL connection pooling", owner: "Infrastructure Team", deadline: "Q4 2026" },
  { priority: "Low", action: "Review worker pod resource limits", owner: "Platform Team", deadline: "Q1 2027" },
]

export default function ReportPanel() {
  const [format, setFormat] = useState<ReportFormat>("Markdown")
  const [generated, setGenerated] = useState(false)
  const [schedule, setSchedule] = useState<"none" | "daily" | "weekly" | "monthly">("none")

  const generate = () => {
    setGenerated(true)
  }

  const emailReport = () => {
    // Placeholder — email delivery to be implemented
  }

  const download = (type: "json" | "markdown") => {
    // Placeholder — file download to be implemented
  }

  return (
    <div className="space-y-6">
      <SectionHeader title="Executive Capacity Report" subtitle="Generate and export capacity planning reports" />

      <div className="bg-white rounded-[18px] border border-[#E8EDF3] p-5 shadow-sm">
        <SectionHeader title="Report Controls" />
        <div className="flex items-center gap-4 mb-4">
          <span className="text-sm font-medium text-gray-600">Format:</span>
          <div className="flex gap-2">
            {formats.map((f) => (
              <button
                key={f}
                onClick={() => setFormat(f)}
                className={`px-4 py-2 text-sm font-medium rounded-xl border transition-colors ${
                  format === f
                    ? "border-[#38B88A] bg-emerald-50 text-[#38B88A]"
                    : "border-[#E8EDF3] text-gray-600 hover:border-gray-300"
                }`}
              >
                {f}
              </button>
            ))}
          </div>
          <div className="ml-auto flex gap-2">
            <button
              onClick={generate}
              className="px-5 py-2 bg-[#38B88A] hover:bg-emerald-600 text-white text-sm font-semibold rounded-xl transition-colors flex items-center gap-2"
            >
              <FileText size={16} /> Generate Report
            </button>
            <button
              onClick={emailReport}
              className="px-5 py-2 border border-[#E8EDF3] hover:border-gray-300 text-gray-700 text-sm font-semibold rounded-xl transition-colors flex items-center gap-2"
            >
              <Mail size={16} /> Email Report
            </button>
          </div>
        </div>

        <div className="flex items-center gap-3 pt-3 border-t border-[#E8EDF3]">
          <Calendar size={14} className="text-gray-400" />
          <span className="text-xs text-gray-500">Scheduled report:</span>
          {(["none", "daily", "weekly", "monthly"] as const).map((s) => (
            <button
              key={s}
              onClick={() => setSchedule(s)}
              className={`px-3 py-1 text-xs font-medium rounded-lg border transition-colors ${
                schedule === s
                  ? "border-[#38B88A] bg-emerald-50 text-[#38B88A]"
                  : "border-[#E8EDF3] text-gray-500 hover:border-gray-300"
              }`}
            >
              {s === "none" ? "No Schedule" : s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {generated ? (
        <>
          <div className="bg-white rounded-[18px] border border-[#E8EDF3] p-5 shadow-sm">
            <SectionHeader
              title="Report Preview"
              subtitle={`Generated ${format} · ${new Date().toLocaleString()}`}
              action={
                <div className="flex gap-2">
                  <button onClick={() => download("json")} className="px-3 py-1.5 text-xs font-medium border border-[#E8EDF3] rounded-lg hover:bg-gray-50 flex items-center gap-1 transition-colors">
                    <Download size={12} /> JSON
                  </button>
                  <button onClick={() => download("markdown")} className="px-3 py-1.5 text-xs font-medium border border-[#E8EDF3] rounded-lg hover:bg-gray-50 flex items-center gap-1 transition-colors">
                    <Download size={12} /> Markdown
                  </button>
                </div>
              }
            />

            <div className="p-4 rounded-xl bg-gray-50 border border-[#E8EDF3] mb-5">
              <h4 className="text-sm font-semibold text-gray-900 mb-2">Executive Summary</h4>
              <p className="text-xs text-gray-600 leading-relaxed">
                This capacity report analyzes the current infrastructure supporting 1,000 concurrent users and projects
                requirements for scaling to 5,000 and 10,000 user tiers. Current resource utilization is at 67% of
                provisioned capacity, providing adequate headroom. Key recommendations include scaling Neo4j to 3 nodes
                to address write contention at 1,800 TPS, implementing LLM fallback providers, and increasing Redis pool
                capacity. Estimated monthly cost at the 5,000-user tier is $24,500, representing a 2.7× increase from the
                current $9,200/mo. All recommendations carry low-to-medium risk with clear mitigation strategies.
              </p>
            </div>

            <div className="grid grid-cols-3 gap-4 mb-5">
              {kpiHighlights.map((k) => (
                <KpiCard key={k.label} title={k.label} value={k.value} subtitle={k.detail} />
              ))}
            </div>

            <div className="grid grid-cols-2 gap-6 mb-5">
              <div>
                <SectionHeader title="Scaling Recommendations" />
                <DataTable
                  columns={[
                    { key: "component", label: "Component" },
                    { key: "current", label: "Current" },
                    { key: "recommended", label: "Recommended" },
                    { key: "reason", label: "Reason" },
                  ]}
                  rows={scalingRecs}
                />
              </div>
              <div>
                <SectionHeader title="Cost Estimates" />
                <DataTable
                  columns={[
                    { key: "tier", label: "Tier" },
                    { key: "cost", label: "Cost" },
                    { key: "breakdown", label: "Breakdown" },
                  ]}
                  rows={costEstimates}
                />
              </div>
            </div>

            <div className="mb-5">
              <SectionHeader title="Risk Assessment" />
              <div className="space-y-2">
                {riskItems.map((r) => (
                  <div key={r.item} className="flex items-start gap-3 p-3 rounded-xl border border-[#E8EDF3]">
                    {r.level === "High" ? <AlertTriangle size={16} className="text-red-500 mt-0.5" /> :
                     r.level === "Medium" ? <HelpCircle size={16} className="text-amber-500 mt-0.5" /> :
                     <CheckCircle2 size={16} className="text-emerald-500 mt-0.5" />}
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium text-gray-900">{r.item}</span>
                        <StatusBadge status={r.level === "High" ? "error" : r.level === "Medium" ? "warning" : "healthy"} label={r.level} />
                      </div>
                      <p className="text-xs text-gray-500 mt-0.5">Mitigation: {r.mitigation}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <SectionHeader title="Action Items" />
              <DataTable
                columns={[
                  {
                    key: "priority",
                    label: "Priority",
                    render: (val: unknown) => <StatusBadge status={val as string === "High" ? "error" : val as string === "Medium" ? "warning" : "healthy"} label={val as string} />,
                  },
                  { key: "action", label: "Action" },
                  { key: "owner", label: "Owner" },
                  { key: "deadline", label: "Deadline" },
                ]}
                rows={actionItems}
              />
            </div>
          </div>

          <div className="flex items-center justify-between p-4 rounded-xl bg-gray-50 border border-[#E8EDF3]">
            <div className="flex items-center gap-3">
              <Clock size={16} className="text-gray-400" />
              <span className="text-sm text-gray-600">Last generated: {new Date().toLocaleString()}</span>
            </div>
            <div className="flex items-center gap-2">
              <Calendar size={14} className="text-gray-400" />
              <span className="text-xs text-gray-500">
                {schedule === "none" ? "No scheduled delivery" : `${schedule} delivery scheduled`}
              </span>
            </div>
          </div>
        </>
      ) : (
        <div className="bg-white rounded-[18px] border border-[#E8EDF3] p-8 shadow-sm flex items-center justify-center">
          <div className="text-center max-w-md">
            <FileText size={40} className="text-gray-300 mx-auto mb-3" />
            <h4 className="text-base font-semibold text-gray-700 mb-1">No Report Generated</h4>
            <p className="text-xs text-gray-400">
              Select a format and click "Generate Report" to create an executive capacity report with scaling recommendations,
              cost estimates, and risk assessment.
            </p>
          </div>
        </div>
      )}
    </div>
  )
}