"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import CortexShell from "@/components/layout/CortexShell"
import { stagger, variants } from "@/lib/motion-tokens"
import {
  usePatchList,
  usePatchDetail,
  usePatchDiff,
  useCreatePatch,
  useValidatePatch,
  useRollbackPatch,
} from "@/hooks/queries/enterprise/useEnterprisePatch"
import { useWorkspaceList } from "@/hooks/queries/enterprise/useEnterpriseWorkspace"
import {
  Activity,
  AlertTriangle,
  ArrowLeftRight,
  BarChart3,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Code2,
  Eye,
  FileCode,
  GitBranch,
  Layers,
  Loader2,
  Plus,
  RotateCcw,
  ScrollText,
  Shield,
  Terminal,
  Trash2,
  XCircle,
  Zap,
} from "lucide-react"

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    draft: "bg-gray-100 text-gray-600",
    validating: "bg-blue-50 text-blue-600",
    validated: "bg-[#F0FDF4] text-[#38B88A]",
    failed: "bg-red-50 text-red-600",
    applied: "bg-purple-50 text-purple-600",
    rolled_back: "bg-amber-50 text-amber-600",
  }
  return (
    <span className={`rounded-full px-2 py-0.5 text-[0.55rem] font-medium capitalize ${colors[status] || "bg-gray-100 text-gray-600"}`}>
      {status}
    </span>
  )
}

function RiskScore({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  const color = pct < 30 ? "text-[#38B88A]" : pct < 60 ? "text-amber-500" : "text-red-500"
  return <span className={`text-sm font-bold ${color}`}>{pct}%</span>
}

export default function EnterprisePatchCenter() {
  const [activeTab, setActiveTab] = useState("library")
  const [selectedPatch, setSelectedPatch] = useState("")
  const [showCreate, setShowCreate] = useState(false)
  const [newPatchWs, setNewPatchWs] = useState("")
  const [newPatchTitle, setNewPatchTitle] = useState("")

  const { data: patches } = usePatchList()
  const { data: patchDetail } = usePatchDetail(selectedPatch)
  const { data: patchDiff } = usePatchDiff(selectedPatch)
  const { data: workspaces } = useWorkspaceList()
  const createMutation = useCreatePatch()
  const validateMutation = useValidatePatch()
  const rollbackMutation = useRollbackPatch()

  const handleCreate = async () => {
    if (!newPatchTitle || !newPatchWs) return
    try {
      await createMutation.mutateAsync({
        workspace_id: newPatchWs,
        title: newPatchTitle,
        files_changed: [],
      })
      setNewPatchTitle("")
      setNewPatchWs("")
      setShowCreate(false)
    } catch (err) {
      console.error("Create patch failed:", err)
    }
  }

  const tabs = [
    { id: "library", label: "Patch Library", icon: ScrollText },
    { id: "detail", label: "Patch Detail", icon: Eye, disabled: !selectedPatch },
  ]

  return (
    <CortexShell title="Enterprise Patch Center" subtitle="Engineering-grade change management — every patch traceable, explainable, and reversible">
      <div className="relative z-10 mx-auto max-w-7xl space-y-6">
        {/* Summary Cards */}
        <motion.div initial="hidden" animate="visible" variants={stagger(0.04, 0.01)} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { icon: ScrollText, label: "Total Patches", value: patches?.length ?? "-", color: "bg-blue-500" },
            { icon: CheckCircle2, label: "Validated", value: patches?.filter(p => p.status === "validated").length ?? "-", color: "bg-[#38B88A]" },
            { icon: AlertTriangle, label: "Failed", value: patches?.filter(p => p.status === "failed").length ?? "-", color: "bg-red-500" },
            { icon: RotateCcw, label: "Rolled Back", value: patches?.filter(p => p.status === "rolled_back").length ?? "-", color: "bg-amber-500" },
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
          <button onClick={() => setShowCreate(!showCreate)}
            className="flex items-center gap-1.5 rounded-lg border border-[#38B88A]/30 px-3 py-1.5 text-[0.65rem] font-medium text-[#38B88A] hover:bg-[#F0FDF4]">
            <Plus className="h-3.5 w-3.5" /> New Patch
          </button>
        </div>

        {/* Patch Library */}
        {activeTab === "library" && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
            {showCreate && (
              <div className="rounded-xl border border-[#38B88A]/30 bg-[#F0FDF4] p-4">
                <h3 className="mb-3 text-sm font-bold text-[#111827]">Create Patch</h3>
                <div className="grid gap-3 sm:grid-cols-2">
                  <select value={newPatchWs} onChange={e => setNewPatchWs(e.target.value)}
                    className="rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] outline-none">
                    <option value="">Select workspace...</option>
                    {workspaces?.map(ws => (
                      <option key={ws.id} value={ws.id}>{ws.name}</option>
                    ))}
                  </select>
                  <input type="text" value={newPatchTitle} onChange={e => setNewPatchTitle(e.target.value)}
                    placeholder="Patch title" className="rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] outline-none" />
                </div>
                <button onClick={handleCreate} disabled={!newPatchTitle || !newPatchWs || createMutation.isPending}
                  className="mt-3 flex items-center gap-2 rounded-lg bg-[#38B88A] px-4 py-2 text-[0.72rem] font-bold text-white disabled:opacity-50">
                  {createMutation.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
                  Create Patch
                </button>
              </div>
            )}

            {patches?.length === 0 ? (
              <div className="flex flex-col items-center justify-center rounded-xl border border-[#E8EDF3] bg-white py-16 text-[#9CA3AF]">
                <FileCode className="mb-3 h-10 w-10 opacity-30" />
                <p className="text-sm">No patches yet. Create your first patch.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {patches?.map((patch) => (
                  <button key={patch.id} onClick={() => { setSelectedPatch(patch.id); setActiveTab("detail") }}
                    className={`w-full rounded-xl border-l-4 p-4 text-left transition-all ${
                      patch.status === "validated" ? "border-l-[#38B88A] bg-white" :
                      patch.status === "failed" ? "border-l-red-400 bg-white" :
                      patch.status === "rolled_back" ? "border-l-amber-400 bg-white" :
                      "border-l-gray-300 bg-white"
                    } hover:shadow-sm`}>
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0 flex-1">
                        <div className="mb-1 flex items-center gap-2">
                          <StatusBadge status={patch.status} />
                          {patch.categories?.map(c => (
                            <span key={c} className="rounded bg-[#F4F7FA] px-1.5 py-0.5 text-[0.5rem] text-[#6B7280]">{c}</span>
                          ))}
                          <span className="text-[0.55rem] text-[#9CA3AF]">{patch.engineer}</span>
                        </div>
                        <h3 className="text-[0.82rem] font-bold text-[#111827]">{patch.title}</h3>
                        <p className="mt-0.5 text-[0.65rem] text-[#6B7280] line-clamp-1">{patch.description}</p>
                        <div className="mt-2 flex flex-wrap items-center gap-3 text-[0.55rem] text-[#9CA3AF]">
                          <span className="flex items-center gap-1"><FileCode className="h-3 w-3" />{patch.files_changed?.length ?? 0} files</span>
                          <span className="flex items-center gap-1"><Code2 className="h-3 w-3 text-[#38B88A]" />+{patch.lines_added}</span>
                          <span className="flex items-center gap-1"><Code2 className="h-3 w-3 text-red-400" />-{patch.lines_deleted}</span>
                          <span className="flex items-center gap-1"><Shield className="h-3 w-3" />Risk: <RiskScore score={patch.validation_results?.risk_score ?? 0} /></span>
                        </div>
                      </div>
                      <div className="shrink-0 text-right">
                        <p className="text-[0.5rem] text-[#9CA3AF]">{new Date(patch.created_at).toLocaleDateString()}</p>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </motion.div>
        )}

        {/* Patch Detail */}
        {activeTab === "detail" && patchDetail && (
          <motion.div key={patchDetail.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
            {/* Header */}
            <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="mb-1 flex items-center gap-2">
                    <StatusBadge status={patchDetail.status} />
                    <span className="text-[0.55rem] text-[#9CA3AF]">{patchDetail.id}</span>
                  </div>
                  <h2 className="text-lg font-bold text-[#111827]">{patchDetail.title}</h2>
                  <p className="mt-0.5 text-[0.7rem] text-[#6B7280]">{patchDetail.description}</p>
                </div>
                <div className="flex items-center gap-2">
                  <button onClick={() => validateMutation.mutate(patchDetail.id)}
                    className="flex items-center gap-1.5 rounded-lg bg-[#38B88A]/10 px-3 py-1.5 text-[0.65rem] font-medium text-[#38B88A] hover:bg-[#38B88A]/20">
                    <CheckCircle2 className="h-3.5 w-3.5" /> Validate
                  </button>
                  <button onClick={() => rollbackMutation.mutate(patchDetail.id)}
                    className="flex items-center gap-1.5 rounded-lg bg-amber-50 px-3 py-1.5 text-[0.65rem] font-medium text-amber-600 hover:bg-amber-100">
                    <RotateCcw className="h-3.5 w-3.5" /> Rollback
                  </button>
                </div>
              </div>
            </div>

            {/* Files & Stats */}
            <div className="grid gap-5 lg:grid-cols-2">
              <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                <h3 className="mb-3 text-sm font-bold text-[#111827]">Changed Files ({patchDetail.files_changed?.length ?? 0})</h3>
                {patchDetail.files_changed?.length > 0 ? (
                  <div className="space-y-2">
                    {patchDetail.files_changed.map((f, i) => (
                      <div key={i} className="flex items-center gap-2 rounded-lg border border-[#E8EDF3] px-3 py-2">
                        <FileCode className="h-3.5 w-3.5 shrink-0 text-[#6B7280]" />
                        <div className="min-w-0 flex-1">
                          <p className="text-[0.65rem] font-medium text-[#111827] truncate">{f.filename}</p>
                          <div className="flex gap-2 text-[0.5rem] text-[#9CA3AF]">
                            <span className="text-[#38B88A]">+{f.lines_added ?? f.added ?? 0}</span>
                            <span className="text-red-400">-{f.lines_removed ?? f.removed ?? 0}</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-[0.7rem] text-[#9CA3AF]">No files recorded yet.</p>
                )}
              </div>

              <div className="space-y-4">
                {/* Diff Summary */}
                <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                  <h3 className="mb-3 text-sm font-bold text-[#111827]">Diff Summary</h3>
                  {patchDiff ? (
                    <div className="space-y-3">
                      <div className="grid grid-cols-3 gap-3">
                        <div className="rounded-lg bg-[#F0FDF4] px-3 py-2 text-center">
                          <p className="text-lg font-bold text-[#38B88A]">+{patchDiff.total_added}</p>
                          <p className="text-[0.55rem] text-[#6B7280]">Added</p>
                        </div>
                        <div className="rounded-lg bg-red-50 px-3 py-2 text-center">
                          <p className="text-lg font-bold text-red-500">-{patchDiff.total_removed}</p>
                          <p className="text-[0.55rem] text-[#6B7280]">Removed</p>
                        </div>
                        <div className="rounded-lg bg-gray-50 px-3 py-2 text-center">
                          <p className="text-lg font-bold text-[#6B7280]">{patchDiff.total_files}</p>
                          <p className="text-[0.55rem] text-[#6B7280]">Files</p>
                        </div>
                      </div>
                      <div className="space-y-1">
                        {patchDiff.files?.slice(0, 5).map((f, i) => (
                          <div key={i} className="flex items-center justify-between text-[0.6rem]">
                            <span className="text-[#6B7280] truncate">{f.filename}</span>
                            <span className="flex gap-1.5 shrink-0">
                              <span className="text-[#38B88A]">+{f.added}</span>
                              <span className="text-red-400">-{f.removed}</span>
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <p className="text-[0.7rem] text-[#9CA3AF]">Run validation to generate diff.</p>
                  )}
                </div>

                {/* Validation Results */}
                <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                  <h3 className="mb-3 text-sm font-bold text-[#111827]">Validation</h3>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-[0.65rem]">
                      <span className="text-[#6B7280]">Syntax</span>
                      <span className={`font-medium ${patchDetail.validation_results?.syntax === "passed" ? "text-[#38B88A]" : "text-red-500"}`}>
                        {patchDetail.validation_results?.syntax ?? "pending"}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-[0.65rem]">
                      <span className="text-[#6B7280]">Dependencies</span>
                      <span className={`font-medium ${patchDetail.validation_results?.dependencies === "passed" ? "text-[#38B88A]" : "text-red-500"}`}>
                        {patchDetail.validation_results?.dependencies ?? "pending"}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-[0.65rem]">
                      <span className="text-[#6B7280]">Consistency</span>
                      <span className={`font-medium ${patchDetail.validation_results?.consistency === "passed" ? "text-[#38B88A]" : "text-red-500"}`}>
                        {patchDetail.validation_results?.consistency ?? "pending"}
                      </span>
                    </div>
                    <div className="flex items-center justify-between pt-2 border-t border-[#E8EDF3]">
                      <span className="text-[0.65rem] font-medium text-[#6B7280]">Risk Score</span>
                      <RiskScore score={patchDetail.validation_results?.risk_score ?? 0} />
                    </div>
                  </div>
                  {patchDetail.validation_results?.warnings && patchDetail.validation_results.warnings.length > 0 && (
                    <div className="mt-3 space-y-1">
                      {(patchDetail.validation_results.warnings as string[]).map((w: string, i: number) => (
                        <div key={i} className="flex items-start gap-1.5 text-[0.6rem] text-amber-600">
                          <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
                          <span>{w}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Dependency Analysis */}
            {patchDetail.dependency_analysis && (
              <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                <h3 className="mb-3 text-sm font-bold text-[#111827]">Dependency Analysis</h3>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  {Object.entries((patchDetail.dependency_analysis as any).summary ?? {}).map(([key, val]) => (
                    <div key={key} className="rounded-lg bg-[#FAFBFC] px-3 py-2">
                      <p className="text-[0.55rem] font-medium text-[#9CA3AF] capitalize">{key.replace(/_/g, " ")}</p>
                      <p className="text-sm font-bold text-[#111827]">{String(val)}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Rollback Info */}
            {patchDetail.rollback_patch_id && (
              <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
                <div className="flex items-center gap-2">
                  <RotateCcw className="h-4 w-4 text-amber-500" />
                  <p className="text-[0.72rem] text-amber-700">
                    This patch has a rollback: <strong>{patchDetail.rollback_patch_id}</strong>
                  </p>
                </div>
              </div>
            )}
          </motion.div>
        )}
      </div>
    </CortexShell>
  )
}
