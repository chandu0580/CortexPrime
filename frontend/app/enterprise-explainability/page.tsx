"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import CortexShell from "@/components/layout/CortexShell"
import { stagger, variants } from "@/lib/motion-tokens"
import {
  useExplainableMissions,
  useMissionExplanation,
  useMissionTimeline,
  useMissionReasoning,
  useMissionEvidence,
  useMissionVerification,
  useMissionConfidence,
  useMissionPolicy,
  useExplainabilityDashboard,
} from "@/hooks/queries/enterprise/useEnterpriseExplainability"
import {
  Activity,
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Cpu,
  Eye,
  FileText,
  GitBranch,
  Loader2,
  Search,
  Shield,
  Target,
} from "lucide-react"

function PhaseBadge({ phase }: { phase: string }) {
  const colors: Record<string, string> = {
    planning: "bg-blue-100 text-blue-700",
    reasoning: "bg-purple-100 text-purple-700",
    simulation: "bg-indigo-100 text-indigo-700",
    decision: "bg-amber-100 text-amber-700",
    workflow: "bg-[#F0FDF4] text-[#38B88A]",
    verification: "bg-teal-100 text-teal-700",
    recovery: "bg-red-100 text-red-700",
    approval: "bg-pink-100 text-pink-700",
    completion: "bg-green-100 text-green-700",
    failure: "bg-red-100 text-red-700",
    governance: "bg-gray-100 text-gray-700",
  }
  return (
    <span className={`rounded px-1.5 py-0.5 text-[0.6rem] font-medium ${colors[phase] || "bg-gray-100 text-gray-600"}`}>
      {phase}
    </span>
  )
}

function ConfidenceMeter({ value }: { value: number }) {
  const pct = Math.round(value * 100)
  const color = pct >= 80 ? "bg-[#38B88A]" : pct >= 50 ? "bg-amber-500" : "bg-red-500"
  return (
    <div className="flex items-center gap-3">
      <div className="h-3 flex-1 overflow-hidden rounded-full bg-[#F3F4F6]">
        <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`text-sm font-bold ${pct >= 80 ? "text-[#38B88A]" : pct >= 50 ? "text-amber-600" : "text-red-600"}`}>
        {pct}%
      </span>
    </div>
  )
}

function RiskGauge({ level }: { level: string }) {
  const colors: Record<string, string> = {
    low: "text-[#38B88A] bg-[#F0FDF4] border-[#38B88A]",
    medium: "text-amber-600 bg-amber-50 border-amber-400",
    high: "text-red-600 bg-red-50 border-red-400",
  }
  return (
    <span className={`rounded-full border px-3 py-1 text-sm font-medium capitalize ${colors[level] || "text-gray-600 bg-gray-50 border-gray-300"}`}>
      {level} risk
    </span>
  )
}

function TimelineSection({ executionId }: { executionId: string }) {
  const { data: timeline, isLoading } = useMissionTimeline(executionId)
  const [expanded, setExpanded] = useState(false)
  const display = expanded ? timeline : timeline?.slice(0, 8)

  if (isLoading) return <div className="flex justify-center py-4"><Loader2 className="h-4 w-4 animate-spin text-[#6B7280]" /></div>
  if (!timeline || timeline.length === 0) return <p className="py-4 text-center text-[0.78rem] text-[#9CA3AF]">No timeline data.</p>

  return (
    <div>
      <div className="space-y-0">
        {display?.map((entry, i) => (
          <div key={i} className="flex gap-3 pb-2 last:pb-0">
            <div className="flex flex-col items-center">
              <div className={`h-2.5 w-2.5 shrink-0 rounded-full ${
                entry.phase === "failure" || entry.phase === "recovery" ? "bg-red-400" :
                entry.phase === "completion" ? "bg-[#38B88A]" : "bg-blue-400"
              }`} />
              {i < (display?.length ?? 0) - 1 && <div className="mt-1 h-full w-px bg-[#E8EDF3]" />}
            </div>
            <div className="min-w-0 flex-1 pb-2">
              <div className="flex items-center gap-2">
                <PhaseBadge phase={entry.phase} />
                <span className="text-[0.6rem] text-[#9CA3AF]">{entry.source}</span>
              </div>
              <p className="mt-0.5 text-[0.72rem] text-[#111827]">{entry.message || entry.event_type}</p>
              <p className="text-[0.6rem] text-[#6B7280]">{entry.agent} — {entry.status}</p>
            </div>
          </div>
        ))}
      </div>
      {timeline.length > 8 && (
        <button onClick={() => setExpanded(!expanded)} className="mt-2 flex items-center gap-1 text-[0.7rem] font-medium text-[#38B88A]">
          {expanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
          {expanded ? "Show less" : `Show all ${timeline.length} entries`}
        </button>
      )}
    </div>
  )
}

function ReasoningSection({ executionId }: { executionId: string }) {
  const { data: reasoning, isLoading } = useMissionReasoning(executionId)

  if (isLoading) return <div className="flex justify-center py-4"><Loader2 className="h-4 w-4 animate-spin text-[#6B7280]" /></div>
  if (!reasoning || reasoning.length === 0) return <p className="py-4 text-center text-[0.78rem] text-[#9CA3AF]">No reasoning data.</p>

  return (
    <div className="space-y-2">
      {reasoning.map((r, i) => (
        <div key={i} className="rounded-lg border border-[#E8EDF3] bg-white p-3">
          <div className="flex items-start gap-2.5">
            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#38B88A] text-[0.6rem] font-bold text-white">
              {r.step}
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="text-[0.72rem] font-medium text-[#111827]">{r.decision}</span>
                <PhaseBadge phase={r.event_type} />
              </div>
              {r.rationale && (
                <p className="mt-0.5 text-[0.7rem] text-[#6B7280]">{r.rationale}</p>
              )}
              <p className="mt-0.5 text-[0.6rem] text-[#9CA3AF]">{r.agent}</p>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

function EvidenceSection({ executionId }: { executionId: string }) {
  const { data: evidence, isLoading } = useMissionEvidence(executionId)
  const [expanded, setExpanded] = useState(false)
  const display = expanded ? evidence : evidence?.slice(0, 8)

  if (isLoading) return <div className="flex justify-center py-4"><Loader2 className="h-4 w-4 animate-spin text-[#6B7280]" /></div>
  if (!evidence || evidence.length === 0) return <p className="py-4 text-center text-[0.78rem] text-[#9CA3AF]">No evidence data.</p>

  const sourceColors: Record<string, string> = {
    replay_event: "border-l-blue-400",
    knowledge_graph: "border-l-purple-400",
    verification: "border-l-teal-400",
  }

  return (
    <div>
      <div className="space-y-2">
        {display?.map((ev, i) => (
          <div key={i} className={`rounded-r-lg border border-l-4 border-[#E8EDF3] p-3 ${sourceColors[ev.source] || "border-l-gray-400"}`}>
            <div className="flex items-center gap-2">
              <span className="rounded bg-[#F4F7FA] px-1.5 py-0.5 text-[0.6rem] font-medium text-[#6B7280]">{ev.source}</span>
              <span className="text-[0.6rem] text-[#9CA3AF]">{ev.event_type}</span>
            </div>
            <p className="mt-1 text-[0.7rem] text-[#111827] line-clamp-2">{ev.content}</p>
            {ev.url && <p className="mt-0.5 text-[0.6rem] text-blue-500">{ev.url}</p>}
          </div>
        ))}
      </div>
      {evidence.length > 8 && (
        <button onClick={() => setExpanded(!expanded)} className="mt-2 flex items-center gap-1 text-[0.7rem] font-medium text-[#38B88A]">
          {expanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
          {expanded ? "Show less" : `Show all ${evidence.length} entries`}
        </button>
      )}
    </div>
  )
}

function VerificationSection({ executionId }: { executionId: string }) {
  const { data: verification, isLoading } = useMissionVerification(executionId)

  if (isLoading) return <div className="flex justify-center py-4"><Loader2 className="h-4 w-4 animate-spin text-[#6B7280]" /></div>
  if (!verification) return <p className="py-4 text-center text-[0.78rem] text-[#9CA3AF]">No verification data.</p>

  const results = verification.results || []
  const passed = results.filter(r => r.verified).length
  const failed = results.filter(r => !r.verified).length
  return (
    <div className="space-y-3">
      <div className="flex gap-4">
        <div className="rounded-lg bg-[#F0FDF4] px-3 py-2 text-center">
          <p className="text-lg font-bold text-[#38B88A]">{passed}</p>
          <p className="text-[0.6rem] text-[#6B7280]">Passed</p>
        </div>
        <div className="rounded-lg bg-red-50 px-3 py-2 text-center">
          <p className="text-lg font-bold text-red-600">{failed}</p>
          <p className="text-[0.6rem] text-[#6B7280]">Failed</p>
        </div>
        <div className="rounded-lg bg-gray-50 px-3 py-2 text-center">
          <p className="text-lg font-bold text-[#6B7280]">{results.length}</p>
          <p className="text-[0.6rem] text-[#6B7280]">Total</p>
        </div>
      </div>
      <div className="space-y-2">
        {results.map((r, i) => (
          <div key={i} className="flex items-center gap-2 rounded-lg border border-[#E8EDF3] px-3 py-2">
            {r.verified
              ? <CheckCircle2 className="h-4 w-4 shrink-0 text-[#38B88A]" />
              : <AlertTriangle className="h-4 w-4 shrink-0 text-red-500" />
            }
            <div className="min-w-0 flex-1">
              <p className="text-[0.7rem] text-[#111827]">{r.method} — {r.verified ? "Passed" : "Failed"}</p>
              <p className="text-[0.6rem] text-[#6B7280]">{r.evidence_data}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function ConfidenceSection({ executionId }: { executionId: string }) {
  const { data: confidence, isLoading } = useMissionConfidence(executionId)

  if (isLoading) return <div className="flex justify-center py-4"><Loader2 className="h-4 w-4 animate-spin text-[#6B7280]" /></div>
  if (!confidence) return <p className="py-4 text-center text-[0.78rem] text-[#9CA3AF]">No confidence data.</p>

  const componentLabels: Record<string, string> = {
    completion: "Completion",
    verification: "Verification",
    recovery: "Recovery Impact",
    approval: "Approval Rate",
    audit: "Audit Trail",
    consistency: "Consistency",
  }

  return (
    <div className="space-y-4">
      <div>
        <p className="mb-1 text-[0.7rem] font-medium text-[#6B7280]">Overall Confidence</p>
        <ConfidenceMeter value={confidence.overall} />
      </div>
      <div className="space-y-2">
        {Object.entries(confidence.components || {}).map(([key, val]) => (
          <div key={key}>
            <div className="mb-0.5 flex justify-between text-[0.65rem]">
              <span className="text-[#6B7280]">{componentLabels[key] || key}</span>
              <span className="font-medium text-[#111827]">{(val * 100).toFixed(0)}%</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-[#F3F4F6]">
              <div className={`h-full rounded-full ${val >= 0 ? "bg-[#38B88A]" : "bg-red-400"}`}
                style={{ width: `${Math.abs(val) * 100}%` }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function PoliciesSection({ executionId }: { executionId: string }) {
  const { data: policies } = useMissionPolicy(executionId)

  if (!policies || policies.length === 0) return <p className="py-4 text-center text-[0.78rem] text-[#9CA3AF]">No policy evaluations.</p>

  return (
    <div className="space-y-2">
      {policies.map((p, i) => (
        <div key={i} className="flex items-center gap-2 rounded-lg border border-[#E8EDF3] bg-white px-3 py-2">
          <Shield className={`h-4 w-4 shrink-0 ${
            p.outcome === "approved" || p.outcome === "allowed" ? "text-[#38B88A]" :
            p.outcome === "rejected" || p.outcome === "blocked" ? "text-red-500" : "text-amber-500"
          }`} />
          <div className="min-w-0 flex-1">
            <p className="text-[0.7rem] font-medium text-[#111827]">{p.policy}</p>
            <p className="text-[0.6rem] text-[#6B7280]">{p.outcome} — {p.reason}</p>
          </div>
          <span className={`rounded px-1.5 py-0.5 text-[0.55rem] font-medium capitalize ${
            p.risk_level === "high" ? "bg-red-50 text-red-600" :
            p.risk_level === "medium" ? "bg-amber-50 text-amber-600" : "bg-gray-50 text-gray-600"
          }`}>{p.risk_level}</span>
        </div>
      ))}
    </div>
  )
}

export default function EnterpriseExplainabilityCenter() {
  const [selectedMission, setSelectedMission] = useState("")
  const [searchQuery, setSearchQuery] = useState("")
  const [activeTab, setActiveTab] = useState("summary")

  const { data: missions } = useExplainableMissions(200)
  const { data: explanation, isLoading: explanationLoading } = useMissionExplanation(selectedMission)
  const { data: dashboard } = useExplainabilityDashboard()

  const filteredMissions = missions?.filter(m =>
    !searchQuery || m.objective?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    m.execution_id?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    m.template_name?.toLowerCase().includes(searchQuery.toLowerCase())
  ) ?? []

  const tabs = [
    { id: "summary", label: "Summary", icon: Eye },
    { id: "timeline", label: "Timeline", icon: Activity },
    { id: "reasoning", label: "Reasoning", icon: Cpu },
    { id: "evidence", label: "Evidence", icon: FileText },
    { id: "verification", label: "Verification", icon: CheckCircle2 },
    { id: "confidence", label: "Confidence", icon: BarChart3 },
    { id: "policies", label: "Policies", icon: Shield },
  ]

  const summary = explanation?.summary
  const confidence = explanation?.confidence

  return (
    <CortexShell title="Enterprise Explainability Center" subtitle="Complete decision intelligence for every AI mission — transparent, auditable, and verifiable">
      <div className="relative z-10 mx-auto max-w-7xl space-y-6">
        {/* Dashboard Summary */}
        <motion.div initial="hidden" animate="visible" variants={stagger(0.04, 0.01)} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {[
            { icon: Target, label: "Total Missions", value: dashboard?.total_missions ?? "-", color: "bg-blue-500" },
            { icon: CheckCircle2, label: "Completed", value: dashboard?.completed_missions ?? "-", color: "bg-[#38B88A]" },
            { icon: AlertTriangle, label: "Failed", value: dashboard?.failed_missions ?? "-", color: "bg-red-500" },
            { icon: Activity, label: "Running", value: dashboard?.running_missions ?? "-", color: "bg-amber-500" },
            { icon: Eye, label: "Explainable", value: dashboard?.explainable_missions ?? "-", color: "bg-purple-500" },
          ].map((stat, i) => {
            const Icon = stat.icon
            return (
              <motion.div key={i} variants={variants.fadeUp} className="rounded-xl border border-[#E8EDF3] bg-white p-4">
                <div className="flex items-center gap-3">
                  <div className={`rounded-lg p-2.5 ${stat.color}`}><Icon className="h-4 w-4 text-white" /></div>
                  <div>
                    <p className="text-[0.7rem] font-medium text-[#6B7280]">{stat.label}</p>
                    <p className="text-xl font-bold text-[#111827]">{stat.value}</p>
                  </div>
                </div>
              </motion.div>
            )
          })}
        </motion.div>

        {/* Mission Selector */}
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="rounded-xl border border-[#E8EDF3] bg-white p-4">
          <div className="mb-3 flex items-center gap-2">
            <Search className="h-4 w-4 text-[#9CA3AF]" />
            <input
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Search missions by objective, ID, or template..."
              className="flex-1 border-0 bg-transparent text-sm text-[#111827] outline-none placeholder-[#9CA3AF]"
            />
            {searchQuery && (
              <button onClick={() => setSearchQuery("")} className="text-[0.65rem] text-[#6B7280] hover:text-[#111827]">Clear</button>
            )}
          </div>
          <div className="flex flex-wrap gap-1.5">
            {filteredMissions.slice(0, 30).map((m) => (
              <button
                key={m.execution_id}
                onClick={() => setSelectedMission(m.execution_id)}
                className={`rounded-full border px-2.5 py-1 text-[0.65rem] font-medium transition-all ${
                  selectedMission === m.execution_id
                    ? "border-[#38B88A] bg-[#38B88A] text-white"
                    : "border-[#E8EDF3] bg-white text-[#6B7280] hover:border-[#38B88A]/30"
                }`}
              >
                {m.objective?.slice(0, 40) || m.execution_id.slice(0, 8)}
              </button>
            ))}
          </div>
        </motion.div>

        {/* Mission Explanation */}
        {selectedMission && (
          <motion.div key={selectedMission} initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-5">
            {explanationLoading ? (
              <div className="flex items-center justify-center py-16 text-[#6B7280]">
                <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Loading explanation...
              </div>
            ) : explanation ? (
              <>
                {/* Summary Header */}
                <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <h2 className="text-lg font-bold text-[#111827]">{summary?.mission_objective || "Mission"}</h2>
                      <p className="mt-0.5 text-[0.78rem] text-[#6B7280]">
                        Template: {summary?.template_name} — Execution: {selectedMission.slice(0, 12)}...
                      </p>
                      <div className="mt-3 flex flex-wrap gap-3">
                        <span className={`rounded-full px-3 py-1 text-[0.7rem] font-medium capitalize ${
                          summary?.status === "completed" ? "bg-[#F0FDF4] text-[#38B88A]" :
                          summary?.status === "failed" ? "bg-red-50 text-red-600" : "bg-amber-50 text-amber-600"
                        }`}>{summary?.status}</span>
                        {summary?.risk_level && <RiskGauge level={summary.risk_level} />}
                        {confidence && <ConfidenceMeter value={confidence.overall} />}
                      </div>
                    </div>
                    <div className="shrink-0 text-right text-[0.65rem] text-[#9CA3AF]">
                      <p>{summary?.total_steps ?? 0} steps</p>
                      <p>{summary?.total_decisions ?? 0} decisions</p>
                    </div>
                  </div>

                  {/* Quick stats */}
                  <div className="mt-4 grid gap-3 border-t border-[#E8EDF3] pt-4 sm:grid-cols-2 lg:grid-cols-4">
                    {[
                      { label: "Connector Calls", value: explanation.connector_calls?.length ?? 0, icon: GitBranch },
                      { label: "Recoveries", value: summary?.total_recoveries ?? 0, icon: AlertTriangle },
                      { label: "Approvals", value: summary?.total_approvals ?? 0, icon: Shield },
                      { label: "Artifacts", value: summary?.total_artifacts ?? 0, icon: FileText },
                    ].map((s, i) => {
                      const Icon = s.icon
                      return (
                        <div key={i} className="flex items-center gap-2 rounded-lg bg-[#FAFBFC] px-3 py-2">
                          <Icon className="h-3.5 w-3.5 text-[#6B7280]" />
                          <span className="text-[0.65rem] text-[#6B7280]">{s.label}</span>
                          <span className="ml-auto text-sm font-bold text-[#111827]">{s.value}</span>
                        </div>
                      )
                    })}
                  </div>
                </div>

                {/* Tab Navigation */}
                <div className="flex flex-wrap gap-1 rounded-xl border border-[#E8EDF3] bg-white p-1">
                  {tabs.map((tab) => {
                    const TabIcon = tab.icon
                    const isActive = activeTab === tab.id
                    return (
                      <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id)}
                        className={`flex items-center gap-2 rounded-lg px-4 py-2 text-[0.78rem] font-medium transition-all ${
                          isActive ? "bg-[#38B88A] text-white shadow-sm" : "text-[#6B7280] hover:bg-[#F4F7FA]"
                        }`}
                      >
                        <TabIcon className="h-4 w-4" />
                        {tab.label}
                      </button>
                    )
                  })}
                </div>

                {/* Tab Content */}
                <motion.div key={activeTab} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
                  {activeTab === "summary" && (
                    <div className="grid gap-5 lg:grid-cols-2">
                      <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                        <h3 className="mb-3 text-sm font-bold text-[#111827]">Alternatives Considered</h3>
                        {explanation.alternatives?.alternatives?.length > 0 ? (
                          <div className="space-y-2">
                            {explanation.alternatives.alternatives.map((a, i) => (
                              <div key={i} className="rounded-lg border border-[#E8EDF3] p-3">
                                <p className="text-[0.72rem] font-medium text-[#111827] capitalize">{a.type} ({a.count}x)</p>
                                <p className="text-[0.65rem] text-[#6B7280]">{a.description}</p>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="text-[0.78rem] text-[#9CA3AF]">No alternatives were needed.</p>
                        )}
                      </div>
                      <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                        <h3 className="mb-3 text-sm font-bold text-[#111827]">Learning Context</h3>
                        {explanation.learning_context?.lessons_applied?.length > 0 && (
                          <div className="space-y-2">
                            <p className="text-[0.65rem] font-medium text-[#6B7280]">Lessons Applied</p>
                            {explanation.learning_context.lessons_applied.map((l, i) => (
                              <div key={i} className="rounded bg-[#FAFBFC] p-2">
                                <p className="text-[0.7rem] text-[#111827]">{l.content}</p>
                              </div>
                            ))}
                          </div>
                        )}
                        {explanation.learning_context?.recovery_strategies?.length > 0 && (
                          <div className="mt-3 space-y-2">
                            <p className="text-[0.65rem] font-medium text-[#6B7280]">Recovery Strategies Available</p>
                            <div className="flex flex-wrap gap-1.5">
                              {explanation.learning_context.recovery_strategies.map((r, i) => (
                                <span key={i} className="rounded-full bg-amber-50 px-2 py-0.5 text-[0.6rem] text-amber-700">
                                  {r.type} ({r.count})
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                      <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                        <h3 className="mb-3 text-sm font-bold text-[#111827]">Connector Operations</h3>
                        {explanation.connector_calls?.length > 0 ? (
                          <div className="space-y-2">
                            {explanation.connector_calls.map((c, i) => (
                              <div key={i} className="flex items-center gap-2 rounded-lg border border-[#E8EDF3] px-3 py-2">
                                <div className={`h-2 w-2 shrink-0 rounded-full ${
                                  c.status === "completed" ? "bg-[#38B88A]" : c.status === "failed" ? "bg-red-400" : "bg-amber-400"
                                }`} />
                                <div className="min-w-0 flex-1">
                                  <p className="text-[0.7rem] font-medium text-[#111827]">{c.connector}.{c.operation}</p>
                                  <p className="text-[0.6rem] text-[#6B7280]">{c.description}</p>
                                </div>
                                <span className="text-[0.55rem] capitalize text-[#9CA3AF]">{c.status}</span>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="text-[0.78rem] text-[#9CA3AF]">No connector calls recorded.</p>
                        )}
                      </div>
                      <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                        <h3 className="mb-3 text-sm font-bold text-[#111827]">Data Sources</h3>
                        <div className="space-y-2">
                          {Object.entries(explanation.sources || {}).map(([key, val]) => (
                            <div key={key} className="flex items-center justify-between rounded-lg bg-[#FAFBFC] px-3 py-2">
                              <span className="text-[0.7rem] text-[#6B7280] capitalize">{key.replace(/_/g, " ")}</span>
                              <span className="text-sm font-bold text-[#111827]">{val}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}

                  {activeTab === "timeline" && (
                    <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                      <h3 className="mb-4 text-sm font-bold text-[#111827]">Mission Timeline</h3>
                      <TimelineSection executionId={selectedMission} />
                    </div>
                  )}

                  {activeTab === "reasoning" && (
                    <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                      <h3 className="mb-4 text-sm font-bold text-[#111827]">Reasoning Chain</h3>
                      <ReasoningSection executionId={selectedMission} />
                    </div>
                  )}

                  {activeTab === "evidence" && (
                    <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                      <h3 className="mb-4 text-sm font-bold text-[#111827]">Evidence Explorer</h3>
                      <EvidenceSection executionId={selectedMission} />
                    </div>
                  )}

                  {activeTab === "verification" && (
                    <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                      <h3 className="mb-4 text-sm font-bold text-[#111827]">Verification Results</h3>
                      <VerificationSection executionId={selectedMission} />
                    </div>
                  )}

                  {activeTab === "confidence" && (
                    <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                      <h3 className="mb-4 text-sm font-bold text-[#111827]">Confidence Analysis</h3>
                      <ConfidenceSection executionId={selectedMission} />
                    </div>
                  )}

                  {activeTab === "policies" && (
                    <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                      <h3 className="mb-4 text-sm font-bold text-[#111827]">Policy Evaluations</h3>
                      <PoliciesSection executionId={selectedMission} />
                    </div>
                  )}
                </motion.div>
              </>
            ) : (
              <div className="flex flex-col items-center justify-center py-16 text-[#6B7280]">
                <Eye className="mb-3 h-10 w-10 opacity-30" />
                <p className="text-sm">No explanation data available for this mission.</p>
              </div>
            )}
          </motion.div>
        )}
      </div>
    </CortexShell>
  )
}
