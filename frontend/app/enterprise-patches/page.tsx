"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import CortexShell from "@/components/layout/CortexShell"
import { stagger, variants } from "@/lib/motion-tokens"
import {
  usePatchPlans,
  usePatchCandidates,
  useGeneratePatches,
  useValidateCandidate,
  useCompareCandidates,
  useAnalyzeRefactor,
  useApplyRefactor,
} from "@/hooks/queries/enterprise/useEnterprisePatch"
import type { ValidationResult } from "@/types/patch-pipeline"
import {
  Activity,
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Code2,
  FileCode,
  GitBranch,
  GitCompare,
  Loader2,
  RefreshCw,
  Search,
  Shield,
  Trash2,
  Wand2,
  XCircle,
  Zap,
} from "lucide-react"

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    planned: "bg-blue-50 text-blue-600",
    generated: "bg-purple-50 text-purple-600",
    validating: "bg-amber-50 text-amber-600",
    validated: "bg-[#F0FDF4] text-[#38B88A]",
    failed: "bg-red-50 text-red-600",
    selected: "bg-green-50 text-green-700",
    rejected: "bg-gray-100 text-gray-500",
    compared: "bg-indigo-50 text-indigo-600",
    refactored: "bg-teal-50 text-teal-600",
  }
  return (
    <span className={`rounded-full px-2 py-0.5 text-[0.55rem] font-medium capitalize ${colors[status] || "bg-gray-100 text-gray-600"}`}>
      {status}
    </span>
  )
}

function ApproachBadge({ approach }: { approach: string }) {
  const labels: Record<string, string> = {
    direct_fix: "Direct Fix",
    minimal_change: "Minimal",
    refactored: "Refactored",
    alternative: "Alternative",
    conservative: "Conservative",
  }
  const colors: Record<string, string> = {
    direct_fix: "bg-blue-50 text-blue-600 border-blue-200",
    minimal_change: "bg-green-50 text-green-600 border-green-200",
    refactored: "bg-purple-50 text-purple-600 border-purple-200",
    alternative: "bg-amber-50 text-amber-600 border-amber-200",
    conservative: "bg-gray-50 text-gray-600 border-gray-200",
  }
  return (
    <span className={`rounded border px-1.5 py-0.5 text-[0.5rem] font-medium ${colors[approach] || "bg-gray-50 text-gray-600 border-gray-200"}`}>
      {labels[approach] || approach}
    </span>
  )
}

function SeverityBadge({ severity }: { severity: string }) {
  const colors: Record<string, string> = {
    low: "bg-blue-50 text-blue-600",
    medium: "bg-amber-50 text-amber-600",
    high: "bg-red-50 text-red-600",
    critical: "bg-red-100 text-red-700",
  }
  return (
    <span className={`rounded px-1.5 py-0.5 text-[0.5rem] font-medium ${colors[severity] || "bg-gray-100 text-gray-600"}`}>
      {severity}
    </span>
  )
}

export default function EnterprisePatchPipeline() {
  const [activeTab, setActiveTab] = useState("dashboard")
  const [description, setDescription] = useState("")
  const [inputType, setInputType] = useState("bug")
  const [selectedPlanId, setSelectedPlanId] = useState("")
  const [selectedCandidateId, setSelectedCandidateId] = useState("")
  const [sandboxId, setSandboxId] = useState("")
  const [refactorDir, setRefactorDir] = useState("")

  const { data: plans } = usePatchPlans()
  const { data: candidates } = usePatchCandidates(selectedPlanId)
  const generateMutation = useGeneratePatches()
  const validateMutation = useValidateCandidate()
  const compareMutation = useCompareCandidates()
  const analyzeMutation = useAnalyzeRefactor()
  const applyMutation = useApplyRefactor()

  const handleGenerate = async () => {
    if (!description) return
    try {
      const result = await generateMutation.mutateAsync({
        input_type: inputType,
        description,
        candidate_count: 3,
      })
      setSelectedPlanId(result.plan.plan_id)
      setDescription("")
      setActiveTab("candidates")
    } catch (err) {
      console.error("Generate failed:", err)
    }
  }

  const handleValidate = async () => {
    if (!selectedCandidateId) return
    try {
      await validateMutation.mutateAsync({
        candidate_id: selectedCandidateId,
        sandbox_id: sandboxId,
      })
    } catch (err) {
      console.error("Validate failed:", err)
    }
  }

  const handleCompare = async () => {
    if (!selectedPlanId) return
    try {
      await compareMutation.mutateAsync({ plan_id: selectedPlanId })
    } catch (err) {
      console.error("Compare failed:", err)
    }
  }

  const handleAnalyze = async () => {
    if (!refactorDir) return
    try {
      await analyzeMutation.mutateAsync({ directory: refactorDir })
    } catch (err) {
      console.error("Analyze failed:", err)
    }
  }

  const tabs = [
    { id: "dashboard", label: "Dashboard", icon: Activity },
    { id: "generate", label: "Generate", icon: Zap },
    { id: "candidates", label: "Candidates", icon: GitBranch, disabled: !selectedPlanId },
    { id: "refactor", label: "Refactor", icon: Wand2 },
  ]

  return (
    <CortexShell title="Enterprise Patch Pipeline" subtitle="AI-powered patch generation, validation, and refactoring">
      <div className="relative z-10 mx-auto max-w-7xl space-y-6">
        {/* Summary Cards */}
        <motion.div initial="hidden" animate="visible" variants={stagger(0.04, 0.01)} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { icon: FileCode, label: "Plans", value: plans?.length ?? "-", color: "bg-blue-500" },
            { icon: GitBranch, label: "Candidates", value: candidates?.length ?? (selectedPlanId ? "select" : "-"), color: "bg-purple-500" },
            { icon: CheckCircle2, label: "Validated", value: candidates?.filter(c => c.status === "validated").length ?? "-", color: "bg-[#38B88A]" },
            { icon: AlertTriangle, label: "Failed", value: candidates?.filter(c => c.status === "failed").length ?? "-", color: "bg-red-500" },
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

        {/* Tab Nav */}
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#E8EDF3] bg-white p-1">
          <div className="flex flex-wrap gap-1">
            {tabs.map((tab) => {
              const TabIcon = tab.icon
              const isActive = activeTab === tab.id
              return (
                <button
                  key={tab.id}
                  onClick={() => !tab.disabled && setActiveTab(tab.id)}
                  className={`flex items-center gap-2 rounded-lg px-3.5 py-2 text-[0.75rem] font-medium transition-all ${
                    tab.disabled ? "cursor-not-allowed opacity-40" :
                    isActive ? "bg-[#38B88A] text-white shadow-sm" : "text-[#6B7280] hover:bg-[#F4F7FA]"
                  }`}
                >
                  <TabIcon className="h-3.5 w-3.5" />
                  {tab.label}
                </button>
              )
            })}
          </div>
        </div>

        {/* Dashboard */}
        {activeTab === "dashboard" && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
            {/* Existing Plans */}
            <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
              <h3 className="mb-3 text-sm font-bold text-[#111827]">Existing Plans</h3>
              {plans?.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-[#9CA3AF]">
                  <FileCode className="mb-3 h-8 w-8 opacity-30" />
                  <p className="text-[0.72rem]">No plans yet. Go to Generate to create one.</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {plans?.map((plan) => (
                    <button
                      key={plan.plan_id}
                      onClick={() => { setSelectedPlanId(plan.plan_id); setActiveTab("candidates") }}
                      className={`w-full rounded-lg border-l-4 p-3 text-left transition-all hover:shadow-sm ${
                        plan.risk === "high" ? "border-l-red-400 bg-white" :
                        plan.risk === "medium" ? "border-l-amber-400 bg-white" :
                        "border-l-blue-400 bg-white"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <div className="mb-1 flex items-center gap-2">
                            <StatusBadge status={plan.status} />
                            <span className="rounded bg-[#F4F7FA] px-1.5 py-0.5 text-[0.5rem] text-[#6B7280]">{plan.input_type}</span>
                            <span className="text-[0.5rem] text-[#9CA3AF]">{plan.risk} risk</span>
                          </div>
                          <p className="text-[0.72rem] font-medium text-[#111827] line-clamp-1">{plan.description}</p>
                          <div className="mt-1 flex flex-wrap gap-2 text-[0.5rem] text-[#9CA3AF]">
                            <span>{plan.affected_areas?.join(", ")}</span>
                            <span>·</span>
                            <span>{plan.estimated_files} files</span>
                            <span>·</span>
                            <span>{plan.complexity} complexity</span>
                          </div>
                        </div>
                        <div className="shrink-0 text-right">
                          <p className="text-[0.45rem] text-[#9CA3AF]">{new Date(plan.created_at).toLocaleDateString()}</p>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Quick Actions */}
            <div className="grid gap-4 sm:grid-cols-2">
              <button onClick={() => setActiveTab("generate")}
                className="flex items-center gap-3 rounded-xl border border-[#E8EDF3] bg-white p-4 text-left hover:shadow-sm">
                <div className="rounded-lg bg-blue-50 p-2.5">
                  <Zap className="h-5 w-5 text-blue-500" />
                </div>
                <div>
                  <p className="text-[0.75rem] font-bold text-[#111827]">Generate Patches</p>
                  <p className="text-[0.6rem] text-[#6B7280]">Describe an issue and generate up to 5 candidate approaches</p>
                </div>
              </button>
              <button onClick={() => setActiveTab("refactor")}
                className="flex items-center gap-3 rounded-xl border border-[#E8EDF3] bg-white p-4 text-left hover:shadow-sm">
                <div className="rounded-lg bg-purple-50 p-2.5">
                  <Wand2 className="h-5 w-5 text-purple-500" />
                </div>
                <div>
                  <p className="text-[0.75rem] font-bold text-[#111827]">Analyze Refactoring</p>
                  <p className="text-[0.6rem] text-[#6B7280]">Scan a codebase for dead code, large methods, and complexity</p>
                </div>
              </button>
            </div>
          </motion.div>
        )}

        {/* Generate */}
        {activeTab === "generate" && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
            <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
              <h3 className="mb-4 text-sm font-bold text-[#111827]">New Patch Plan</h3>
              <div className="space-y-4">
                <div>
                  <label className="mb-1 block text-[0.65rem] font-medium text-[#6B7280]">Input Type</label>
                  <select value={inputType} onChange={e => setInputType(e.target.value)}
                    className="w-full rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] outline-none">
                    <option value="bug">Bug Fix</option>
                    <option value="feature">Feature</option>
                    <option value="refactor">Refactoring</option>
                    <option value="security">Security</option>
                    <option value="performance">Performance</option>
                    <option value="docs">Documentation</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-[0.65rem] font-medium text-[#6B7280]">Description</label>
                  <textarea value={description} onChange={e => setDescription(e.target.value)}
                    placeholder="Describe the issue or change needed..."
                    className="w-full rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] outline-none min-h-[100px]" />
                </div>
                <button onClick={handleGenerate} disabled={!description || generateMutation.isPending}
                  className="flex items-center gap-2 rounded-lg bg-[#38B88A] px-4 py-2 text-[0.72rem] font-bold text-white disabled:opacity-50">
                  {generateMutation.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Zap className="h-3.5 w-3.5" />}
                  Generate Candidates
                </button>
              </div>
            </div>

            {generateMutation.data && (
              <div className="rounded-xl border border-[#38B88A]/30 bg-[#F0FDF4] p-4">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-[#38B88A]" />
                  <p className="text-[0.72rem] font-medium text-[#38B88A]">
                    Generated {generateMutation.data.candidates?.length ?? 0} candidates for plan {generateMutation.data.plan?.plan_id?.slice(0, 16)}...
                  </p>
                </div>
              </div>
            )}
          </motion.div>
        )}

        {/* Candidates */}
        {activeTab === "candidates" && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
            {/* Plan Selector */}
            <div className="rounded-xl border border-[#E8EDF3] bg-white p-4">
              <div className="flex items-center gap-3">
                <label className="text-[0.65rem] font-medium text-[#6B7280]">Plan:</label>
                <select value={selectedPlanId} onChange={e => setSelectedPlanId(e.target.value)}
                  className="flex-1 rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] outline-none">
                  <option value="">Select plan...</option>
                  {plans?.map(p => (
                    <option key={p.plan_id} value={p.plan_id}>{p.description.slice(0, 60)}...</option>
                  ))}
                </select>
                <button onClick={handleCompare} disabled={!selectedPlanId || compareMutation.isPending}
                  className="flex items-center gap-1.5 rounded-lg bg-indigo-50 px-3 py-2 text-[0.65rem] font-medium text-indigo-600 hover:bg-indigo-100">
                  {compareMutation.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <GitCompare className="h-3.5 w-3.5" />}
                  Compare
                </button>
              </div>
            </div>

            {/* Candidate Cards */}
            {candidates?.length === 0 ? (
              <div className="flex flex-col items-center justify-center rounded-xl border border-[#E8EDF3] bg-white py-16 text-[#9CA3AF]">
                <GitBranch className="mb-3 h-10 w-10 opacity-30" />
                <p className="text-[0.72rem]">No candidates for this plan. Generate candidates first.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {candidates?.map((candidate) => (
                  <div key={candidate.candidate_id}
                    className={`rounded-xl border p-4 ${
                      candidate.status === "selected" ? "border-[#38B88A] bg-[#F0FDF4]" :
                      candidate.status === "validated" ? "border-green-200 bg-white" :
                      candidate.status === "failed" ? "border-red-200 bg-red-50" :
                      "border-[#E8EDF3] bg-white"
                    }`}>
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0 flex-1">
                        <div className="mb-1 flex items-center gap-2">
                          <ApproachBadge approach={candidate.approach} />
                          <StatusBadge status={candidate.status} />
                          {candidate.score !== null && (
                            <span className="rounded bg-indigo-50 px-1.5 py-0.5 text-[0.5rem] font-medium text-indigo-600">
                              Score: {candidate.score.toFixed(1)}
                            </span>
                          )}
                        </div>
                        <p className="text-[0.65rem] text-[#6B7280] mt-1">{candidate.reasoning}</p>
                        <div className="mt-2 flex flex-wrap items-center gap-3 text-[0.5rem] text-[#9CA3AF]">
                          <span>Confidence: {Math.round(candidate.confidence * 100)}%</span>
                          <span>·</span>
                          <span className="text-[#38B88A]">+{candidate.estimated_impact?.lines_added ?? 0}</span>
                          <span className="text-red-400">-{candidate.estimated_impact?.lines_removed ?? 0}</span>
                          <span>·</span>
                          <span>{candidate.files_changed?.length ?? 0} files</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <button onClick={() => { setSelectedCandidateId(candidate.candidate_id); handleValidate() }}
                          disabled={validateMutation.isPending}
                          className="flex items-center gap-1 rounded-lg border border-[#38B88A]/30 px-2 py-1 text-[0.55rem] font-medium text-[#38B88A] hover:bg-[#F0FDF4]">
                          <RefreshCw className="h-3 w-3" /> Validate
                        </button>
                      </div>
                    </div>

                    {/* Validation Results */}
                    {candidate.validation && (() => {
                      const v = candidate.validation as unknown as ValidationResult
                      return v.status ? (
                        <div className="mt-3 grid grid-cols-4 gap-2 rounded-lg bg-[#FAFBFC] p-2">
                          <div className="text-center">
                            <p className={`text-[0.6rem] font-bold ${v.build?.success ? "text-[#38B88A]" : "text-red-500"}`}>
                              {v.build?.success ? "PASS" : "FAIL"}
                            </p>
                            <p className="text-[0.45rem] text-[#9CA3AF]">Build</p>
                          </div>
                          <div className="text-center">
                            <p className={`text-[0.6rem] font-bold ${v.tests?.success ? "text-[#38B88A]" : "text-red-500"}`}>
                              {v.tests?.success ? `${v.tests.passed}/${v.tests.total}` : "FAIL"}
                            </p>
                            <p className="text-[0.45rem] text-[#9CA3AF]">Tests</p>
                          </div>
                          <div className="text-center">
                            <p className={`text-[0.6rem] font-bold ${v.security?.passed ? "text-[#38B88A]" : "text-red-500"}`}>
                              {v.security?.passed ? "PASS" : (v.security?.warnings ?? 0) > 0 ? "WARN" : "FAIL"}
                            </p>
                            <p className="text-[0.45rem] text-[#9CA3AF]">Security</p>
                          </div>
                          <div className="text-center">
                            <p className="text-[0.6rem] font-bold text-blue-600">
                              {v.coverage?.line_coverage_pct ?? "-"}%
                            </p>
                            <p className="text-[0.45rem] text-[#9CA3AF]">Coverage</p>
                          </div>
                        </div>
                      ) : null
                    })()}
                  </div>
                ))}
              </div>
            )}
          </motion.div>
        )}

        {/* Refactor */}
        {activeTab === "refactor" && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
            <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
              <h3 className="mb-4 text-sm font-bold text-[#111827]">Refactoring Analysis</h3>
              <div className="flex items-center gap-3">
                <input type="text" value={refactorDir} onChange={e => setRefactorDir(e.target.value)}
                  placeholder="Directory path to analyze (e.g., /path/to/repo)"
                  className="flex-1 rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] outline-none" />
                <button onClick={handleAnalyze} disabled={!refactorDir || analyzeMutation.isPending}
                  className="flex items-center gap-2 rounded-lg bg-purple-500 px-4 py-2 text-[0.72rem] font-bold text-white disabled:opacity-50">
                  {analyzeMutation.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Search className="h-3.5 w-3.5" />}
                  Analyze
                </button>
              </div>
            </div>

            {analyzeMutation.data && (
              <div className="space-y-4">
                {/* Summary */}
                <div className="grid grid-cols-3 gap-4">
                  {[
                    { label: "Files Analyzed", value: (analyzeMutation.data as any).files_analyzed ?? 0, color: "bg-blue-500" },
                    { label: "Total Findings", value: (analyzeMutation.data as any).summary?.total_findings ?? 0, color: "bg-amber-500" },
                    { label: "Suggestions", value: (analyzeMutation.data as any).suggestions?.length ?? 0, color: "bg-purple-500" },
                  ].map((s, i) => (
                    <div key={i} className="rounded-xl border border-[#E8EDF3] bg-white p-4">
                      <div className="flex items-center gap-3">
                        <div className={`rounded-lg p-2 ${s.color}`}>
                          <BarChart3 className="h-4 w-4 text-white" />
                        </div>
                        <div>
                          <p className="text-[0.6rem] text-[#6B7280]">{s.label}</p>
                          <p className="text-xl font-bold text-[#111827]">{s.value}</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Findings By Type */}
                {(analyzeMutation.data as any).summary?.by_type && (
                  <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                    <h3 className="mb-3 text-sm font-bold text-[#111827]">Findings by Type</h3>
                    <div className="space-y-2">
                      {Object.entries((analyzeMutation.data as any).summary.by_type as Record<string, number>).map(([type, count]) => (
                        <div key={type} className="flex items-center justify-between text-[0.65rem]">
                          <span className="capitalize text-[#6B7280]">{type.replace(/_/g, " ")}</span>
                          <span className="font-bold text-[#111827]">{count}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Findings List */}
                {(analyzeMutation.data as any).findings?.length > 0 && (
                  <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                    <h3 className="mb-3 text-sm font-bold text-[#111827]">Findings</h3>
                    <div className="space-y-2 max-h-[400px] overflow-y-auto">
                      {((analyzeMutation.data as any).findings as any[]).slice(0, 50).map((finding: any, i: number) => (
                        <div key={i} className="flex items-start gap-3 rounded-lg border border-[#E8EDF3] p-2">
                          <div className="shrink-0">
                            {finding.type === "unused_import" ? <Trash2 className="h-3 w-3 text-blue-400" /> :
                             finding.type === "large_method" ? <FileCode className="h-3 w-3 text-amber-400" /> :
                             finding.type === "high_complexity" ? <GitBranch className="h-3 w-3 text-red-400" /> :
                             <AlertTriangle className="h-3 w-3 text-gray-400" />}
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                              <SeverityBadge severity={finding.severity} />
                              <span className="text-[0.5rem] text-[#9CA3AF]">{finding.file?.split(/[/\\]/).pop()}:{finding.line}</span>
                            </div>
                            <p className="text-[0.6rem] text-[#6B7280] mt-0.5">{finding.message}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Suggestions */}
                {(analyzeMutation.data as any).suggestions?.length > 0 && (
                  <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                    <h3 className="mb-3 text-sm font-bold text-[#111827]">Suggestions</h3>
                    <div className="space-y-2">
                      {((analyzeMutation.data as any).suggestions as any[]).map((suggestion: any, i: number) => (
                        <div key={i} className="flex items-start justify-between gap-3 rounded-lg border border-purple-100 bg-purple-50 p-3">
                          <div>
                            <p className="text-[0.65rem] font-medium text-[#111827]">{suggestion.message}</p>
                            <p className="text-[0.5rem] text-[#6B7280] mt-0.5">{suggestion.file}</p>
                          </div>
                          <button onClick={() => applyMutation.mutate({ suggestion_id: `${suggestion.type}-${i}` })}
                            disabled={applyMutation.isPending}
                            className="shrink-0 rounded-lg bg-purple-500 px-2 py-1 text-[0.5rem] font-medium text-white hover:bg-purple-600">
                            Apply
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </motion.div>
        )}
      </div>
    </CortexShell>
  )
}
