"use client"
import { useState } from "react"
import { motion } from "framer-motion"
import CortexShell from "@/components/layout/CortexShell"
import { stagger, variants } from "@/lib/motion-tokens"
import {
  useExecutionDashboard,
  useExecutions,
  useExecution,
  useCreateExecution,
  useStartAsyncExecution,
  useCancelExecution,
  useRollbackExecution,
  useRetryExecution,
} from "@/hooks/queries/enterprise/useEnterpriseExecution"
import {
  Activity, CheckCircle, XCircle, Clock, Loader2, PlayCircle, StopCircle,
  RotateCcw, Undo2, Plus, Eye, List, BarChart3, GitBranch, Server, Zap,
  AlertTriangle, ExternalLink,
} from "lucide-react"

const tabs = ["Dashboard", "Executions", "Create"]

function StatusBadge({ status }: { status?: string }) {
  const s = (status || "").toLowerCase()
  if (s === "completed" || s === "success")
    return <span className="inline-flex items-center gap-1 text-xs font-medium text-green-600 dark:text-green-400"><CheckCircle size={12} />{status}</span>
  if (s === "failed")
    return <span className="inline-flex items-center gap-1 text-xs font-medium text-red-600 dark:text-red-400"><XCircle size={12} />{status}</span>
  if (s === "running" || s === "pending" || s === "planning" || s.startsWith("workspace") || s.startsWith("analysis") || s.startsWith("patch") || s.startsWith("sandbox") || s.startsWith("git") || s.startsWith("deployment") || s.startsWith("observability") || s.startsWith("learning"))
    return <span className="inline-flex items-center gap-1 text-xs font-medium text-yellow-600 dark:text-yellow-400"><Clock size={12} />{status}</span>
  if (s === "cancelled")
    return <span className="inline-flex items-center gap-1 text-xs font-medium text-gray-500 dark:text-gray-400"><StopCircle size={12} />{status}</span>
  if (s === "rolled_back")
    return <span className="inline-flex items-center gap-1 text-xs font-medium text-orange-600 dark:text-orange-400"><Undo2 size={12} />{status}</span>
  return <span className="inline-flex items-center gap-1 text-xs font-medium text-gray-500 dark:text-gray-400"><Activity size={12} />{status || "unknown"}</span>
}

function KpiCard({ icon: Icon, label, value, color }: { icon: any; label: string; value: number | string; color: string }) {
  return (
    <motion.div variants={variants.fadeIn} className={`rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 ${color}`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">{label}</p>
          <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">{value}</p>
        </div>
        <div className="p-3 rounded-lg bg-gray-100 dark:bg-gray-700">
          <Icon size={24} className={color} />
        </div>
      </div>
    </motion.div>
  )
}

function StageProgress({ current, stages }: { current: string; stages: string[] }) {
  const idx = stages.indexOf(current)
  return (
    <div className="flex items-center gap-1 flex-wrap">
      {stages.map((s, i) => (
        <div key={s} className={`w-2 h-2 rounded-full ${i < idx ? 'bg-green-500' : i === idx ? 'bg-yellow-500 animate-pulse' : 'bg-gray-300 dark:bg-gray-600'}`} title={s} />
      ))}
    </div>
  )
}

export default function EnterpriseExecutionPage() {
  const [activeTab, setActiveTab] = useState("Dashboard")
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const { data: dashboard, isLoading: dashLoading } = useExecutionDashboard()
  const { data: executions, isLoading: execsLoading } = useExecutions()
  const { data: selectedExec, isLoading: selLoading } = useExecution(selectedId || "")

  const createExec = useCreateExecution()
  const startExec = useStartAsyncExecution()
  const cancelExec = useCancelExecution()
  const rollbackExec = useRollbackExecution()
  const retryExec = useRetryExecution()

  const ds = dashboard || {} as any
  const execList = executions || []
  const sel = selectedExec || null

  const stageOrder = ["pending","planning","workspace_prep","analysis","patch_generation","sandbox_execution","git_ops","deployment","observability","learning","completed"]

  const [form, setForm] = useState({ repository: "", branch: "main", objective: "" })

  function handleCreate() {
    createExec.mutate(form, {
      onSuccess: (data) => {
        startExec.mutate({ executionId: data.execution_id })
        setForm({ repository: "", branch: "main", objective: "" })
      },
    })
  }

  return (
    <CortexShell
      title="Enterprise Execution Engine"
      subtitle="Autonomous engineering execution from GitHub event to verified deployment"
    >
      <motion.div initial="hidden" animate="visible" variants={stagger(0.04, 0.01)} className="space-y-6">
        {/* Tabs */}
        <div className="flex flex-wrap gap-2 border-b border-gray-200 dark:border-gray-700 pb-2">
          {tabs.map((tab) => (
            <button key={tab} onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${
                activeTab === tab
                  ? "text-blue-600 dark:text-blue-400 border-b-2 border-blue-600 dark:border-blue-400"
                  : "text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
              }`}>{tab}</button>
          ))}
        </div>

        {/* DASHBOARD */}
        {activeTab === "Dashboard" && (
          <motion.div variants={stagger(0.04, 0.01)} className="space-y-6">
            {dashLoading ? (
              <div className="flex items-center justify-center py-20"><Loader2 size={32} className="animate-spin text-gray-400" /></div>
            ) : (
              <>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
                  <KpiCard icon={BarChart3} label="Total" value={ds.total_executions || 0} color="text-blue-600" />
                  <KpiCard icon={PlayCircle} label="Active" value={ds.active_count || 0} color="text-yellow-600" />
                  <KpiCard icon={CheckCircle} label="Completed" value={ds.completed_count || 0} color="text-green-600" />
                  <KpiCard icon={XCircle} label="Failed" value={ds.failed_count || 0} color="text-red-600" />
                  <KpiCard icon={Activity} label="Cancelled" value={ds.by_status?.cancelled || 0} color="text-gray-500" />
                </div>

                <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
                  <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
                    <h3 className="text-sm font-semibold text-gray-900 dark:text-white">Recent Executions</h3>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="text-xs text-gray-500 dark:text-gray-400 uppercase border-b border-gray-200 dark:border-gray-700">
                        <tr>
                          <th className="text-left px-4 py-2">ID</th>
                          <th className="text-left px-4 py-2">Repository</th>
                          <th className="text-left px-4 py-2">Status</th>
                          <th className="text-left px-4 py-2">Stage</th>
                          <th className="text-left px-4 py-2">Risk</th>
                          <th className="text-right px-4 py-2">Created</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(ds.recent_executions || []).map((ex: any) => (
                          <tr key={ex.execution_id} className="border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50 cursor-pointer" onClick={() => { setSelectedId(ex.execution_id); setActiveTab("Executions") }}>
                            <td className="px-4 py-2 font-mono text-xs text-blue-600 dark:text-blue-400">{ex.execution_id?.slice(0, 16)}</td>
                            <td className="px-4 py-2 text-gray-700 dark:text-gray-300">{ex.repository || "-"}</td>
                            <td className="px-4 py-2"><StatusBadge status={ex.status} /></td>
                            <td className="px-4 py-2"><StageProgress current={ex.current_stage} stages={stageOrder} /></td>
                            <td className="px-4 py-2">
                              <span className={`text-xs font-medium px-2 py-0.5 rounded ${ex.risk_level === 'high' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' : ex.risk_level === 'medium' ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400' : 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'}`}>{ex.risk_level}</span>
                            </td>
                            <td className="px-4 py-2 text-right text-gray-500 dark:text-gray-400 text-xs">{ex.created_at ? new Date(ex.created_at).toLocaleString() : "-"}</td>
                          </tr>
                        ))}
                        {!(ds.recent_executions?.length) && (
                          <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400 dark:text-gray-500">No executions yet — create one in the Create tab.</td></tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </>
            )}
          </motion.div>
        )}

        {/* EXECUTIONS */}
        {activeTab === "Executions" && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* List */}
            <div className="lg:col-span-1 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
              <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-gray-900 dark:text-white">Executions</h3>
                <span className="text-xs text-gray-500 dark:text-gray-400">{execList.length} total</span>
              </div>
              <div className="overflow-y-auto max-h-[70vh]">
                {execsLoading ? (
                  <div className="flex items-center justify-center py-10"><Loader2 size={20} className="animate-spin text-gray-400" /></div>
                ) : execList.length === 0 ? (
                  <div className="px-4 py-8 text-center text-gray-400 dark:text-gray-500 text-sm">No executions found.</div>
                ) : (
                  execList.map((ex: any) => (
                    <div key={ex.execution_id}
                      className={`px-4 py-3 border-b border-gray-100 dark:border-gray-700 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50 ${selectedId === ex.execution_id ? 'bg-blue-50 dark:bg-blue-900/20' : ''}`}
                      onClick={() => setSelectedId(ex.execution_id)}>
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-xs text-blue-600 dark:text-blue-400">{ex.execution_id?.slice(0, 12)}</span>
                        <StatusBadge status={ex.status} />
                      </div>
                      <div className="mt-1 text-xs text-gray-500 dark:text-gray-400 truncate">{ex.repository || ex.objective || "-"}</div>
                      <StageProgress current={ex.current_stage} stages={stageOrder} />
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Detail */}
            <div className="lg:col-span-2 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
              {!selectedId ? (
                <div className="flex items-center justify-center py-20 text-gray-400 dark:text-gray-500"><List size={32} className="mr-2" /> Select an execution</div>
              ) : selLoading ? (
                <div className="flex items-center justify-center py-20"><Loader2 size={24} className="animate-spin text-gray-400" /></div>
              ) : !sel ? (
                <div className="flex items-center justify-center py-20 text-red-500">Execution not found</div>
              ) : (
                <div className="p-4 space-y-4">
                  {/* Header */}
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-sm font-semibold text-gray-900 dark:text-white font-mono">{sel.execution_id}</h3>
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{sel.objective || "No objective"}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      {sel.status === "running" && (
                        <button onClick={() => cancelExec.mutate(sel.execution_id)} className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-lg bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400 hover:bg-red-200 dark:hover:bg-red-900/50"><StopCircle size={14} /> Cancel</button>
                      )}
                      {sel.status === "failed" && (
                        <button onClick={() => retryExec.mutate(sel.execution_id)} className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-lg bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400 hover:bg-yellow-200 dark:hover:bg-yellow-900/50"><RotateCcw size={14} /> Retry</button>
                      )}
                      {sel.status === "completed" && (
                        <button onClick={() => rollbackExec.mutate(sel.execution_id)} className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-lg bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400 hover:bg-orange-200 dark:hover:bg-orange-900/50"><Undo2 size={14} /> Rollback</button>
                      )}
                      <span className="px-3 py-1.5 rounded-lg text-xs font-medium bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300"><StatusBadge status={sel.status} /></span>
                    </div>
                  </div>

                  {/* Meta */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                    <div><span className="text-gray-500 dark:text-gray-400">Repository</span><p className="font-medium text-gray-900 dark:text-white mt-0.5">{sel.repository || "-"}</p></div>
                    <div><span className="text-gray-500 dark:text-gray-400">Branch</span><p className="font-medium text-gray-900 dark:text-white mt-0.5">{sel.branch || "-"}</p></div>
                    <div><span className="text-gray-500 dark:text-gray-400">Risk</span><p className="font-medium mt-0.5"><span className={`px-2 py-0.5 rounded text-xs font-medium ${sel.risk_level === 'high' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' : sel.risk_level === 'medium' ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400' : 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'}`}>{sel.risk_level} ({sel.risk_score})</span></p></div>
                    <div><span className="text-gray-500 dark:text-gray-400">Strategy</span><p className="font-medium text-gray-900 dark:text-white mt-0.5">{sel.deployment_strategy || "-"}</p></div>
                  </div>

                  {sel.pr_url && (
                    <a href={sel.pr_url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 hover:underline">
                      <ExternalLink size={12} /> PR #{sel.pr_number}
                    </a>
                  )}

                  {sel.error_message && (
                    <div className="p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-xs text-red-700 dark:text-red-400">
                      <strong>Error:</strong> {sel.error_message}
                    </div>
                  )}

                  {/* Stage Timeline */}
                  <div>
                    <h4 className="text-xs font-semibold text-gray-700 dark:text-gray-300 mb-2 uppercase tracking-wider">Stage Timeline</h4>
                    <div className="space-y-1">
                      {stageOrder.filter(s => s !== "pending" && s !== "completed").map((stage) => {
                        const sr = sel.stages?.[stage]
                        if (!sr) return null
                        return (
                          <div key={stage} className="flex items-center gap-3 px-3 py-2 rounded-lg bg-gray-50 dark:bg-gray-700/50">
                            <div className={`w-2 h-2 rounded-full ${sr.status === 'completed' ? 'bg-green-500' : sr.status === 'running' ? 'bg-yellow-500 animate-pulse' : sr.status === 'failed' ? 'bg-red-500' : 'bg-gray-300 dark:bg-gray-600'}`} />
                            <div className="flex-1">
                              <div className="flex items-center justify-between">
                                <span className="text-xs font-medium text-gray-700 dark:text-gray-300 capitalize">{stage.replace(/_/g, " ")}</span>
                                <span className="text-xs text-gray-500 dark:text-gray-400">{sr.status}</span>
                              </div>
                              {sr.error && <p className="text-xs text-red-500 mt-0.5">{sr.error}</p>}
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>

                  {/* Timeline */}
                  {sel.timeline?.length > 0 && (
                    <div>
                      <h4 className="text-xs font-semibold text-gray-700 dark:text-gray-300 mb-2 uppercase tracking-wider">Event Timeline</h4>
                      <div className="space-y-1 max-h-48 overflow-y-auto">
                        {sel.timeline.map((entry: any, i: number) => (
                          <div key={i} className="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-400">
                            <span className="text-gray-400 dark:text-gray-500 font-mono">{new Date(entry.timestamp).toLocaleTimeString()}</span>
                            <span className={`capitalize ${entry.status === 'failed' ? 'text-red-500' : 'text-gray-700 dark:text-gray-300'}`}>{entry.stage}</span>
                            <span className="text-gray-400 dark:text-gray-500">—</span>
                            <span className="truncate">{entry.message}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* CREATE */}
        {activeTab === "Create" && (
          <motion.div variants={variants.fadeIn} className="max-w-lg mx-auto rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-6 space-y-4">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white">New Autonomous Execution</h3>
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Repository (org/repo)</label>
                <input type="text" value={form.repository} onChange={(e) => setForm({ ...form, repository: e.target.value })}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500" placeholder="e.g. my-org/my-repo" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Branch</label>
                <input type="text" value={form.branch} onChange={(e) => setForm({ ...form, branch: e.target.value })}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Objective</label>
                <textarea value={form.objective} onChange={(e) => setForm({ ...form, objective: e.target.value })}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500" rows={3} placeholder="What should this execution accomplish?" />
              </div>
              <button onClick={handleCreate} disabled={createExec.isPending || startExec.isPending}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed">
                {createExec.isPending || startExec.isPending ? <Loader2 size={16} className="animate-spin" /> : <Zap size={16} />}
                Create & Start Execution
              </button>
              {createExec.isSuccess && <p className="text-xs text-green-600 dark:text-green-400">Execution created and started!</p>}
              {createExec.isError && <p className="text-xs text-red-600 dark:text-red-400">Failed: {(createExec.error as any)?.message}</p>}
            </div>
          </motion.div>
        )}
      </motion.div>
    </CortexShell>
  )
}
