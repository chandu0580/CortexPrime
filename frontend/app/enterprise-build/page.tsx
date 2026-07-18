"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import CortexShell from "@/components/layout/CortexShell"
import { stagger, variants } from "@/lib/motion-tokens"
import { useBuildList, useCreateBuild, useExecuteBuild, useCancelBuild } from "@/hooks/queries/enterprise/useEnterpriseBuild"
import { useWorkspaceList } from "@/hooks/queries/enterprise/useEnterpriseWorkspace"
import {
  Activity,
  CheckCircle2,
  Cog,
  GitBranch,
  Hammer,
  Loader2,
  Package,
  Play,
  Plus,
  Square,
  Terminal,
  XCircle,
} from "lucide-react"

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    pending: "bg-gray-100 text-gray-600",
    running: "bg-blue-50 text-blue-600",
    passed: "bg-[#F0FDF4] text-[#38B88A]",
    failed: "bg-red-50 text-red-600",
    cancelled: "bg-amber-50 text-amber-600",
  }
  return (
    <span className={`rounded-full px-2 py-0.5 text-[0.55rem] font-medium capitalize ${colors[status] || "bg-gray-100 text-gray-600"}`}>
      {status}
    </span>
  )
}

export default function EnterpriseBuildCenter() {
  const [activeTab, setActiveTab] = useState("builds")
  const [showCreate, setShowCreate] = useState(false)
  const [newBuildWs, setNewBuildWs] = useState("")
  const [newBuildBranch, setNewBuildBranch] = useState("main")

  const { data: builds } = useBuildList()
  const { data: workspaces } = useWorkspaceList()
  const createMutation = useCreateBuild()
  const executeMutation = useExecuteBuild()
  const cancelMutation = useCancelBuild()

  const handleCreate = async () => {
    if (!newBuildWs) return
    try {
      const build = await createMutation.mutateAsync({
        workspace_id: newBuildWs,
        branch: newBuildBranch,
      })
      await executeMutation.mutateAsync(build.id)
      setNewBuildWs("")
      setShowCreate(false)
    } catch (err) {
      console.error("Create build failed:", err)
    }
  }

  const tabs = [
    { id: "builds", label: "Builds", icon: Hammer },
    { id: "artifacts", label: "Artifacts", icon: Package },
  ]

  return (
    <CortexShell title="Build Pipeline" subtitle="Execute, verify, and package builds inside workspaces">
      <div className="relative z-10 mx-auto max-w-7xl space-y-6">
        {/* Summary Cards */}
        <motion.div initial="hidden" animate="visible" variants={stagger(0.04, 0.01)} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { icon: Hammer, label: "Total Builds", value: builds?.length ?? "-", color: "bg-blue-500" },
            { icon: CheckCircle2, label: "Passed", value: builds?.filter(b => b.status === "passed").length ?? "-", color: "bg-[#38B88A]" },
            { icon: XCircle, label: "Failed", value: builds?.filter(b => b.status === "failed").length ?? "-", color: "bg-red-500" },
            { icon: Activity, label: "Running", value: builds?.filter(b => b.status === "running").length ?? "-", color: "bg-purple-500" },
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
                <button key={tab.id} onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-2 rounded-lg px-3.5 py-2 text-[0.75rem] font-medium transition-all ${
                    isActive ? "bg-[#38B88A] text-white shadow-sm" : "text-[#6B7280] hover:bg-[#F4F7FA]"
                  }`}>
                  <TabIcon className="h-3.5 w-3.5" /> {tab.label}
                </button>
              )
            })}
          </div>
          <button onClick={() => setShowCreate(!showCreate)}
            className="flex items-center gap-1.5 rounded-lg border border-[#38B88A]/30 px-3 py-1.5 text-[0.65rem] font-medium text-[#38B88A] hover:bg-[#F0FDF4]">
            <Plus className="h-3.5 w-3.5" /> New Build
          </button>
        </div>

        {/* Builds Tab */}
        {activeTab === "builds" && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
            {showCreate && (
              <div className="rounded-xl border border-[#38B88A]/30 bg-[#F0FDF4] p-4">
                <h3 className="mb-3 text-sm font-bold text-[#111827]">Create Build</h3>
                <div className="grid gap-3 sm:grid-cols-2">
                  <select value={newBuildWs} onChange={e => setNewBuildWs(e.target.value)}
                    className="rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] outline-none">
                    <option value="">Select workspace...</option>
                    {workspaces?.map(ws => (
                      <option key={ws.id} value={ws.id}>{ws.name}</option>
                    ))}
                  </select>
                  <input type="text" value={newBuildBranch} onChange={e => setNewBuildBranch(e.target.value)}
                    placeholder="Branch" className="rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] outline-none" />
                </div>
                <button onClick={handleCreate} disabled={!newBuildWs || createMutation.isPending}
                  className="mt-3 flex items-center gap-2 rounded-lg bg-[#38B88A] px-4 py-2 text-[0.72rem] font-bold text-white disabled:opacity-50">
                  {createMutation.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
                  Create & Execute
                </button>
              </div>
            )}

            <div className="space-y-3">
              {builds?.map((build) => (
                <div key={build.id} className={`rounded-xl border-l-4 p-4 ${
                  build.status === "passed" ? "border-l-[#38B88A]" :
                  build.status === "failed" ? "border-l-red-400" :
                  build.status === "running" ? "border-l-blue-400" :
                  "border-l-gray-300"
                } bg-white`}>
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <div className="mb-1 flex items-center gap-2">
                        <StatusBadge status={build.status} />
                        <span className="text-[0.55rem] text-[#9CA3AF]">{build.id}</span>
                        <span className="flex items-center gap-1 text-[0.55rem] text-[#6B7280]"><GitBranch className="h-3 w-3" />{build.branch}</span>
                      </div>
                      <p className="text-[0.7rem] text-[#6B7280]">Workspace: {build.workspace_id}</p>
                      <div className="mt-2 flex items-center gap-4">
                        {build.status === "running" && (
                          <div className="flex items-center gap-2">
                            <div className="h-1.5 w-24 overflow-hidden rounded-full bg-gray-100">
                              <div className="h-full rounded-full bg-blue-500 transition-all" style={{ width: `${build.progress}%` }} />
                            </div>
                            <span className="text-[0.55rem] text-[#6B7280]">{Math.round(build.progress)}%</span>
                            <span className="text-[0.55rem] text-blue-500">{build.current_step}</span>
                          </div>
                        )}
                        <span className="text-[0.55rem] text-[#9CA3AF]">{build.artifacts?.length ?? 0} artifacts</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {build.status === "pending" && (
                        <button onClick={() => executeMutation.mutate(build.id)}
                          className="rounded-lg p-1.5 text-[#38B88A] hover:bg-[#F0FDF4]">
                          <Play className="h-4 w-4" />
                        </button>
                      )}
                      {build.status === "running" && (
                        <button onClick={() => cancelMutation.mutate(build.id)}
                          className="rounded-lg p-1.5 text-red-500 hover:bg-red-50">
                          <Square className="h-4 w-4" />
                        </button>
                      )}
                    </div>
                  </div>
                  {build.log?.length > 0 && build.status === "running" && (
                    <div className="mt-3 max-h-20 overflow-y-auto rounded-lg bg-[#1E293B] p-2 font-mono text-[0.5rem] text-[#94A3B8]">
                      {build.log.slice(-5).map((entry: any, i: number) => (
                        <div key={i} className="flex gap-2">
                          <span className="shrink-0 text-[#64748B]">{entry.timestamp?.split("T")[1]?.split(".")[0]}</span>
                          <span>{entry.message}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
              {(!builds || builds.length === 0) && (
                <div className="flex flex-col items-center rounded-xl border border-[#E8EDF3] bg-white py-16 text-[#9CA3AF]">
                  <Hammer className="mb-3 h-10 w-10 opacity-30" />
                  <p className="text-sm">No builds yet.</p>
                </div>
              )}
            </div>
          </motion.div>
        )}

        {/* Artifacts Tab */}
        {activeTab === "artifacts" && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-3">
            {builds?.filter(b => b.artifacts?.length > 0).flatMap(b =>
              (b.artifacts ?? []).map((art, i) => (
                <div key={`${b.id}-${i}`} className="rounded-xl border border-[#E8EDF3] bg-white p-4">
                  <div className="flex items-center gap-3">
                    <div className="rounded-lg bg-purple-50 p-2"><Package className="h-4 w-4 text-purple-500" /></div>
                    <div className="min-w-0 flex-1">
                      <p className="text-[0.78rem] font-medium text-[#111827]">{art.name}</p>
                      <p className="text-[0.55rem] text-[#6B7280] truncate">{art.path}</p>
                      <div className="mt-1 flex gap-3 text-[0.5rem] text-[#9CA3AF]">
                        <span>{art.type}</span>
                        <span>{(art.size_bytes / 1024).toFixed(1)} KB</span>
                        <span>Build: {b.id}</span>
                      </div>
                    </div>
                  </div>
                </div>
              ))
            )}
            {builds?.every(b => !b.artifacts?.length) && (
              <div className="flex flex-col items-center rounded-xl border border-[#E8EDF3] bg-white py-16 text-[#9CA3AF]">
                <Package className="mb-3 h-10 w-10 opacity-30" />
                <p className="text-sm">No artifacts generated yet.</p>
              </div>
            )}
          </motion.div>
        )}
      </div>
    </CortexShell>
  )
}
