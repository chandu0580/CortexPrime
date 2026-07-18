"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import CortexShell from "@/components/layout/CortexShell"
import { stagger, variants } from "@/lib/motion-tokens"
import {
  BrainCircuit, ListChecks, GitBranch, GitPullRequest, BugPlay,
  GanttChart, FileText, Activity, BarChart3, RotateCcw, ShieldCheck,
  Zap, Code2, TestTube, Rocket, Undo2, Siren,
  Plus, RefreshCw, Trash2, Play, Loader2, CheckCircle, Clock,
  AlertTriangle, XCircle, ArrowRight, Eye, ExternalLink,
} from "lucide-react"
import {
  useEngineeringExecutiveDashboard,
  useSupportedTaskTypes,
  useEngineeringTasks,
  useEngineeringTask,
  useCreateEngineeringTask,
  useDeleteEngineeringTask,
  useEngineeringPlans,
  useEngineeringPlan,
  useCreateEngineeringPlan,
  useExecuteEngineeringPlan,
  useEngineeringExecutionStatus,
  useEngineeringReports,
  useEngineeringReport,
  useGenerateEngineeringReport,
} from "@/hooks/queries/enterprise/useEnterpriseEngineeringExecutive"
import type {
  EngineeringTask,
  EngineeringPlan,
  EngineeringStage,
  EngineeringReport,
  RecoveryEntry,
  SupportedTaskType,
} from "@/types/engineering-executive"

type Tab = "overview" | "tasks" | "plans" | "reports"

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    pending: "bg-yellow-50 text-yellow-600",
    running: "bg-blue-50 text-blue-600",
    completed: "bg-green-50 text-green-600",
    failed: "bg-red-50 text-red-600",
    created: "bg-gray-100 text-gray-600",
    planned: "bg-purple-50 text-purple-600",
    executing: "bg-blue-50 text-blue-600",
    done: "bg-green-50 text-green-600",
  }
  return (
    <span className={`rounded-full px-2 py-0.5 text-[0.55rem] font-medium capitalize ${colors[status] || "bg-gray-100 text-gray-600"}`}>
      {status}
    </span>
  )
}

function StageIcon({ type }: { type: string }) {
  const map: Record<string, React.ElementType> = {
    analyze: BrainCircuit,
    plan: ListChecks,
    code: Code2,
    git_ops: GitBranch,
    review: GitPullRequest,
    test: TestTube,
    build: Rocket,
    patch: BugPlay,
    deliver: Rocket,
    rollback: Undo2,
    recover: RotateCcw,
    escalate: Siren,
  }
  const Icon = map[type] || Activity
  return <Icon className="h-3.5 w-3.5" />
}

export default function EnterpriseEngineeringExecutivePage() {
  const [activeTab, setActiveTab] = useState<Tab>("overview")
  const [showCreateTask, setShowCreateTask] = useState(false)
  const [taskDescription, setTaskDescription] = useState("")
  const [taskRepoUrl, setTaskRepoUrl] = useState("")
  const [taskBranch, setTaskBranch] = useState("")
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null)
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null)

  const { data: dashboard } = useEngineeringExecutiveDashboard()
  const { data: supportedTypes } = useSupportedTaskTypes()
  const { data: tasks = [], refetch: refetchTasks } = useEngineeringTasks()
  const { data: plans = [], refetch: refetchPlans } = useEngineeringPlans()
  const { data: reports = [], refetch: refetchReports } = useEngineeringReports()
  const createTask = useCreateEngineeringTask()
  const deleteTask = useDeleteEngineeringTask()
  const createPlan = useCreateEngineeringPlan()
  const executePlan = useExecuteEngineeringPlan()
  const generateReport = useGenerateEngineeringReport()

  const selectedTask = (tasks as EngineeringTask[]).find((t) => t.task_id === selectedTaskId)
  const selectedPlan = (plans as EngineeringPlan[]).find((p) => p.plan_id === selectedPlanId)

  const { data: executionStatus } = useEngineeringExecutionStatus(selectedPlanId ?? "")

  const handleCreateTask = async () => {
    const trimmed = taskDescription.trim()
    if (!trimmed) return
    try {
      await createTask.mutateAsync({
        description: trimmed,
        repoUrl: taskRepoUrl.trim() || undefined,
        branch: taskBranch.trim() || undefined,
      })
      setTaskDescription("")
      setTaskRepoUrl("")
      setTaskBranch("")
      setShowCreateTask(false)
      refetchTasks()
    } catch { /* ignore */ }
  }

  const handleDeleteTask = async (taskId: string) => {
    try {
      await deleteTask.mutateAsync(taskId)
      if (selectedTaskId === taskId) setSelectedTaskId(null)
      refetchTasks()
    } catch { /* ignore */ }
  }

  const handleCreatePlan = async (taskId: string) => {
    try {
      const plan = await createPlan.mutateAsync(taskId) as EngineeringPlan
      setSelectedPlanId(plan.plan_id)
      setActiveTab("plans")
      refetchPlans()
    } catch { /* ignore */ }
  }

  const handleExecutePlan = async (planId: string) => {
    try {
      await executePlan.mutateAsync(planId)
      setSelectedPlanId(planId)
      refetchPlans()
    } catch { /* ignore */ }
  }

  const handleGenerateReport = async (planId: string) => {
    try {
      await generateReport.mutateAsync(planId)
      refetchReports()
    } catch { /* ignore */ }
  }

  const tabs = [
    { id: "overview" as Tab, label: "Overview", icon: BarChart3 },
    { id: "tasks" as Tab, label: "Tasks", icon: ListChecks },
    { id: "plans" as Tab, label: "Plans", icon: GanttChart },
    { id: "reports" as Tab, label: "Reports", icon: FileText },
  ]

  const kpiCards = [
    { icon: BrainCircuit, label: "Total Tasks", value: dashboard?.total_tasks ?? "-", color: "bg-blue-500" },
    { icon: GanttChart, label: "Total Plans", value: dashboard?.total_plans ?? "-", color: "bg-purple-500" },
    { icon: FileText, label: "Total Reports", value: dashboard?.total_reports ?? "-", color: "bg-amber-500" },
    { icon: CheckCircle, label: "Completed Plans", value: dashboard?.plans_by_status?.completed ?? (dashboard?.plans_by_status?.done ?? "-"), color: "bg-[#38B88A]" },
  ]

  return (
    <CortexShell title="Engineering Executive Center" subtitle="Autonomous engineering brain — plan, execute, and deliver engineering work at scale">
      <div className="relative z-10 mx-auto max-w-7xl space-y-6">
        {/* KPI Cards */}
        <motion.div initial="hidden" animate="visible" variants={stagger(0.04, 0.01)} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {kpiCards.map((stat, i) => {
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

        {/* Create Task Button + Form */}
        <div className="flex items-center justify-between rounded-xl border border-[#E8EDF3] bg-white p-3">
          <div className="flex items-center gap-2">
            <BrainCircuit className="h-4 w-4 text-[#6B7280]" />
            <span className="text-[0.72rem] font-medium text-[#6B7280]">New Engineering Task</span>
          </div>
          <button
            onClick={() => setShowCreateTask(!showCreateTask)}
            className="flex items-center gap-1.5 rounded-lg bg-blue-500 px-3 py-1.5 text-[0.68rem] font-bold text-white hover:bg-blue-600"
          >
            {showCreateTask ? <RotateCcw className="h-3 w-3" /> : <Plus className="h-3 w-3" />}
            {showCreateTask ? "Close" : "Create Task"}
          </button>
        </div>

        <AnimatePresence>
          {showCreateTask && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="overflow-hidden rounded-xl border border-blue-200 bg-blue-50 p-4"
            >
              <h3 className="mb-3 text-sm font-bold text-[#111827]">Define Engineering Task</h3>
              <div className="space-y-3">
                <textarea
                  value={taskDescription}
                  onChange={(e) => setTaskDescription(e.target.value)}
                  placeholder="Describe the engineering task…"
                  rows={3}
                  className="w-full rounded-lg border border-blue-200 px-3 py-2 text-[0.78rem] outline-none"
                />
                <div className="grid gap-3 sm:grid-cols-2">
                  <input
                    type="text"
                    value={taskRepoUrl}
                    onChange={(e) => setTaskRepoUrl(e.target.value)}
                    placeholder="Repo URL (optional)"
                    className="rounded-lg border border-blue-200 px-3 py-2 text-[0.78rem] outline-none"
                  />
                  <input
                    type="text"
                    value={taskBranch}
                    onChange={(e) => setTaskBranch(e.target.value)}
                    placeholder="Branch (optional)"
                    className="rounded-lg border border-blue-200 px-3 py-2 text-[0.78rem] outline-none"
                  />
                </div>
                <button
                  onClick={handleCreateTask}
                  disabled={!taskDescription.trim() || createTask.isPending}
                  className="flex items-center gap-2 rounded-lg bg-blue-500 px-4 py-2 text-[0.72rem] font-bold text-white disabled:opacity-50"
                >
                  {createTask.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <BrainCircuit className="h-3.5 w-3.5" />}
                  Create Task
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Tab Nav */}
        <div className="flex flex-wrap items-center gap-1 rounded-xl border border-[#E8EDF3] bg-white p-1">
          {tabs.map((tab) => {
            const TabIcon = tab.icon
            const isActive = activeTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 rounded-lg px-3.5 py-2 text-[0.75rem] font-medium transition-all ${
                  isActive ? "bg-[#38B88A] text-white shadow-sm" : "text-[#6B7280] hover:bg-[#F4F7FA]"
                }`}
              >
                <TabIcon className="h-3.5 w-3.5" />
                {tab.label}
              </button>
            )
          })}
        </div>

        {/* Overview Tab */}
        {activeTab === "overview" && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
            {/* Dashboard Stats */}
            {dashboard && (
              <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                <h3 className="mb-4 text-sm font-bold text-[#111827]">Dashboard Statistics</h3>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  <div className="rounded-lg border border-[#E8EDF3] p-3">
                    <p className="text-[0.65rem] font-medium text-[#6B7280]">Tasks by Status</p>
                    <div className="mt-2 space-y-1">
                      {Object.entries(dashboard.tasks_by_status).map(([status, count]) => (
                        <div key={status} className="flex items-center justify-between text-[0.7rem]">
                          <span className="text-[#111827] capitalize">{status}</span>
                          <span className="font-bold text-[#111827]">{count}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="rounded-lg border border-[#E8EDF3] p-3">
                    <p className="text-[0.65rem] font-medium text-[#6B7280]">Plans by Status</p>
                    <div className="mt-2 space-y-1">
                      {Object.entries(dashboard.plans_by_status).map(([status, count]) => (
                        <div key={status} className="flex items-center justify-between text-[0.7rem]">
                          <span className="text-[#111827] capitalize">{status}</span>
                          <span className="font-bold text-[#111827]">{count}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="rounded-lg border border-[#E8EDF3] p-3">
                    <p className="text-[0.65rem] font-medium text-[#6B7280]">Plans by Type</p>
                    <div className="mt-2 space-y-1">
                      {Object.entries(dashboard.plans_by_type).map(([type, count]) => (
                        <div key={type} className="flex items-center justify-between text-[0.7rem]">
                          <span className="text-[#111827]">{type}</span>
                          <span className="font-bold text-[#111827]">{count}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Supported Task Types */}
            {supportedTypes && supportedTypes.length > 0 && (
              <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                <h3 className="mb-4 text-sm font-bold text-[#111827]">Supported Task Types</h3>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {supportedTypes.map((type) => (
                    <div key={type.type} className="rounded-lg border border-[#E8EDF3] p-3">
                      <div className="flex items-center gap-2">
                        <BrainCircuit className="h-4 w-4 text-blue-500" />
                        <span className="text-[0.72rem] font-bold text-[#111827]">{type.label}</span>
                      </div>
                      <p className="mt-1 text-[0.6rem] text-[#6B7280]">Type: {type.type}</p>
                      <div className="mt-2 flex flex-wrap gap-1">
                        {type.stages.map((stage) => (
                          <span key={stage} className="rounded bg-gray-100 px-1.5 py-0.5 text-[0.5rem] font-medium text-gray-600">
                            {stage}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        )}

        {/* Tasks Tab */}
        {activeTab === "tasks" && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-[#111827]">Engineering Tasks ({tasks.length})</h3>
              <button onClick={() => refetchTasks()} className="rounded-lg border border-[#E8EDF3] p-2 text-[#6B7280] hover:bg-[#F4F7FA]">
                <RefreshCw className="h-3.5 w-3.5" />
              </button>
            </div>
            {tasks.length === 0 ? (
              <div className="flex flex-col items-center justify-center rounded-xl border border-[#E8EDF3] bg-white py-16 text-[#9CA3AF]">
                <ListChecks className="mb-3 h-10 w-10 opacity-30" />
                <p className="text-[0.72rem]">No engineering tasks yet. Create one above.</p>
              </div>
            ) : (
              <div className="space-y-2">
                {tasks.map((task) => (
                  <motion.div
                    key={task.task_id}
                    layout
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    className="rounded-xl border border-[#E8EDF3] bg-white"
                  >
                    <button
                      onClick={() => setSelectedTaskId(selectedTaskId === task.task_id ? null : task.task_id)}
                      className="flex w-full items-center justify-between p-4 text-left"
                    >
                      <div className="flex items-center gap-3 min-w-0 flex-1">
                        <BrainCircuit className="h-4 w-4 shrink-0 text-[#6B7280]" />
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <span className="text-[0.72rem] font-medium text-[#111827] truncate">{task.description}</span>
                            <StatusBadge status={task.status} />
                          </div>
                          <p className="mt-0.5 text-[0.5rem] text-[#9CA3AF]">
                            {task.task_type} · {new Date(task.created_at).toLocaleDateString()}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {task.repo_url && <Code2 className="h-3 w-3 text-[#9CA3AF]" />}
                        <ArrowRight className={`h-3.5 w-3.5 text-[#9CA3AF] transition-transform ${selectedTaskId === task.task_id ? "rotate-90" : ""}`} />
                      </div>
                    </button>
                    <AnimatePresence>
                      {selectedTaskId === task.task_id && (
                        <motion.div
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: "auto" }}
                          exit={{ opacity: 0, height: 0 }}
                          className="overflow-hidden border-t border-[#E8EDF3]"
                        >
                          <div className="p-4 space-y-3">
                            <div className="grid grid-cols-2 gap-3 text-[0.65rem]">
                              <div>
                                <span className="text-[#6B7280]">Task ID:</span>
                                <span className="ml-1 text-[#111827] font-mono">{task.task_id.slice(0, 16)}</span>
                              </div>
                              <div>
                                <span className="text-[#6B7280]">Type:</span>
                                <span className="ml-1 text-[#111827]">{task.task_label}</span>
                              </div>
                              <div>
                                <span className="text-[#6B7280]">Confidence:</span>
                                <span className="ml-1 text-[#111827]">{(task.confidence * 100).toFixed(0)}%</span>
                              </div>
                              <div>
                                <span className="text-[#6B7280]">Status:</span>
                                <span className="ml-1"><StatusBadge status={task.status} /></span>
                              </div>
                              {task.repo_url && (
                                <div className="col-span-2">
                                  <span className="text-[#6B7280]">Repo:</span>
                                  <span className="ml-1 text-[#111827]">{task.repo_url}</span>
                                  {task.branch && <span className="ml-2 text-[#9CA3AF]">→ {task.branch}</span>}
                                </div>
                              )}
                            </div>
                            <div className="flex gap-2">
                              {!task.plan_id && (
                                <button
                                  onClick={() => handleCreatePlan(task.task_id)}
                                  disabled={createPlan.isPending}
                                  className="flex items-center gap-1.5 rounded-lg bg-purple-500 px-3 py-1.5 text-[0.65rem] font-bold text-white disabled:opacity-50"
                                >
                                  {createPlan.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : <GanttChart className="h-3 w-3" />}
                                  Create Plan
                                </button>
                              )}
                              <button
                                onClick={() => handleDeleteTask(task.task_id)}
                                className="flex items-center gap-1.5 rounded-lg border border-red-200 px-3 py-1.5 text-[0.65rem] font-medium text-red-600 hover:bg-red-50"
                              >
                                <Trash2 className="h-3 w-3" />
                                Delete
                              </button>
                            </div>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </motion.div>
                ))}
              </div>
            )}
          </motion.div>
        )}

        {/* Plans Tab */}
        {activeTab === "plans" && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-[#111827]">Engineering Plans ({plans.length})</h3>
              <button onClick={() => refetchPlans()} className="rounded-lg border border-[#E8EDF3] p-2 text-[#6B7280] hover:bg-[#F4F7FA]">
                <RefreshCw className="h-3.5 w-3.5" />
              </button>
            </div>
            {plans.length === 0 ? (
              <div className="flex flex-col items-center justify-center rounded-xl border border-[#E8EDF3] bg-white py-16 text-[#9CA3AF]">
                <GanttChart className="mb-3 h-10 w-10 opacity-30" />
                <p className="text-[0.72rem]">No plans yet. Create a plan from a task.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {plans.map((plan) => (
                  <motion.div
                    key={plan.plan_id}
                    layout
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="rounded-xl border border-[#E8EDF3] bg-white"
                  >
                    <button
                      onClick={() => setSelectedPlanId(selectedPlanId === plan.plan_id ? null : plan.plan_id)}
                      className="flex w-full items-center justify-between p-4 text-left"
                    >
                      <div className="flex items-center gap-3 min-w-0 flex-1">
                        <GanttChart className="h-4 w-4 shrink-0 text-purple-500" />
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <span className="text-[0.72rem] font-medium text-[#111827] truncate">{plan.task_label}</span>
                            <StatusBadge status={plan.status} />
                          </div>
                          <p className="mt-0.5 text-[0.5rem] text-[#9CA3AF]">
                            {plan.task_type} · {plan.stages.length} stages · {plan.participating_subsystems.length} subsystems
                          </p>
                        </div>
                      </div>
                      <ArrowRight className={`h-3.5 w-3.5 text-[#9CA3AF] transition-transform ${selectedPlanId === plan.plan_id ? "rotate-90" : ""}`} />
                    </button>
                    <AnimatePresence>
                      {selectedPlanId === plan.plan_id && (
                        <motion.div
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: "auto" }}
                          exit={{ opacity: 0, height: 0 }}
                          className="overflow-hidden border-t border-[#E8EDF3]"
                        >
                          <div className="p-4 space-y-4">
                            {/* Plan Info */}
                            <div className="grid grid-cols-2 gap-3 text-[0.65rem]">
                              <div>
                                <span className="text-[#6B7280]">Plan ID:</span>
                                <span className="ml-1 text-[#111827] font-mono">{plan.plan_id.slice(0, 16)}</span>
                              </div>
                              <div>
                                <span className="text-[#6B7280]">Current Stage:</span>
                                <span className="ml-1 text-[#111827]">{plan.current_stage_index} / {plan.stages.length}</span>
                              </div>
                              <div>
                                <span className="text-[#6B7280]">Subsystems:</span>
                                <span className="ml-1 text-[#111827]">{plan.participating_subsystems.join(", ")}</span>
                              </div>
                              {plan.repo_url && (
                                <div>
                                  <span className="text-[#6B7280]">Repo:</span>
                                  <span className="ml-1 text-[#111827]">{plan.repo_url}</span>
                                </div>
                              )}
                            </div>

                            {/* Execution Status */}
                            {executionStatus && selectedPlanId === plan.plan_id && (
                              <div className="rounded-lg border border-blue-100 bg-blue-50 p-3">
                                <div className="flex items-center gap-2 mb-2">
                                  <Activity className="h-3.5 w-3.5 text-blue-500" />
                                  <span className="text-[0.65rem] font-bold text-[#111827]">Execution Status: {executionStatus.status}</span>
                                </div>
                                {executionStatus.stages.map((s) => (
                                  <div key={s.stage_index} className="flex items-center gap-2 py-1 text-[0.6rem]">
                                    <div className={`w-1.5 h-1.5 rounded-full ${
                                      s.status === "completed" ? "bg-green-400" :
                                      s.status === "failed" ? "bg-red-400" :
                                      s.status === "running" ? "bg-blue-400 animate-pulse" :
                                      "bg-gray-300"
                                    }`} />
                                    <span className="text-[#111827] font-medium">{s.stage_type}</span>
                                    <span className="text-[#6B7280]">retry {s.retry_count}</span>
                                    {s.error && <span className="text-red-500 truncate">{s.error}</span>}
                                  </div>
                                ))}
                              </div>
                            )}

                            {/* Stages */}
                            <div>
                              <h4 className="mb-2 text-[0.65rem] font-bold text-[#111827]">Stages ({plan.stages.length})</h4>
                              <div className="space-y-1.5">
                                {plan.stages.map((stage) => (
                                  <div key={stage.stage_id} className="flex items-center gap-3 rounded-lg border border-[#E8EDF3] p-2.5">
                                    <StageIcon type={stage.stage_type} />
                                    <div className="flex-1 min-w-0">
                                      <div className="flex items-center gap-2">
                                        <span className="text-[0.65rem] font-medium text-[#111827]">{stage.stage_type}</span>
                                        <StatusBadge status={stage.status} />
                                        {stage.retry_count > 0 && (
                                          <span className="text-[0.5rem] text-amber-500">retry {stage.retry_count}/{stage.max_retries}</span>
                                        )}
                                      </div>
                                      <p className="text-[0.5rem] text-[#9CA3AF]">
                                        {stage.subsystem}{stage.error ? ` · Error: ${stage.error}` : ""}
                                      </p>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>

                            {/* Recovery Log */}
                            {plan.recovery_log.length > 0 && (
                              <div>
                                <h4 className="mb-2 text-[0.65rem] font-bold text-[#111827]">Recovery Log ({plan.recovery_log.length})</h4>
                                <div className="space-y-1">
                                  {plan.recovery_log.map((entry, i) => (
                                    <div key={i} className="flex items-center gap-2 text-[0.6rem] text-[#6B7280] py-1">
                                      <RotateCcw className="h-3 w-3 text-amber-500" />
                                      <span className="font-medium text-[#111827] capitalize">{entry.action}</span>
                                      <span className="text-[#9CA3AF]">stage {entry.stage_index} ({entry.stage_type})</span>
                                      <span className="ml-auto text-[#9CA3AF]">{new Date(entry.timestamp).toLocaleString()}</span>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}

                            {/* Actions */}
                            <div className="flex flex-wrap gap-2">
                              <button
                                onClick={() => handleExecutePlan(plan.plan_id)}
                                disabled={executePlan.isPending || plan.status === "running" || plan.status === "executing"}
                                className="flex items-center gap-1.5 rounded-lg bg-[#38B88A] px-3 py-1.5 text-[0.65rem] font-bold text-white disabled:opacity-50"
                              >
                                {executePlan.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
                                Execute
                              </button>
                              <button
                                onClick={() => handleGenerateReport(plan.plan_id)}
                                disabled={generateReport.isPending}
                                className="flex items-center gap-1.5 rounded-lg border border-[#E8EDF3] px-3 py-1.5 text-[0.65rem] font-medium text-[#6B7280] hover:bg-[#F4F7FA] disabled:opacity-50"
                              >
                                {generateReport.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : <FileText className="h-3 w-3" />}
                                Generate Report
                              </button>
                            </div>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </motion.div>
                ))}
              </div>
            )}
          </motion.div>
        )}

        {/* Reports Tab */}
        {activeTab === "reports" && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-[#111827]">Generated Reports ({reports.length})</h3>
              <button onClick={() => refetchReports()} className="rounded-lg border border-[#E8EDF3] p-2 text-[#6B7280] hover:bg-[#F4F7FA]">
                <RefreshCw className="h-3.5 w-3.5" />
              </button>
            </div>
            {reports.length === 0 ? (
              <div className="flex flex-col items-center justify-center rounded-xl border border-[#E8EDF3] bg-white py-16 text-[#9CA3AF]">
                <FileText className="mb-3 h-10 w-10 opacity-30" />
                <p className="text-[0.72rem]">No reports yet. Generate one from a plan.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {reports.map((report) => (
                  <motion.div
                    key={report.report_id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="rounded-xl border border-[#E8EDF3] bg-white p-4"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <FileText className="h-4 w-4 text-amber-500" />
                          <span className="text-[0.72rem] font-bold text-[#111827]">{report.task_label}</span>
                          <StatusBadge status={report.overall_status} />
                        </div>
                        <div className="mt-1.5 flex flex-wrap items-center gap-3 text-[0.5rem] text-[#9CA3AF]">
                          <span>{report.task_type}</span>
                          <span>{report.completed_stages}/{report.total_stages} stages</span>
                          <span>{report.total_duration_seconds}s</span>
                          <span>{report.subsystems_used.length} subsystems</span>
                          <span>{new Date(report.generated_at).toLocaleString()}</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <button
                          onClick={() => window.alert(JSON.stringify(report, null, 2))}
                          className="flex items-center gap-1 rounded-lg border border-[#E8EDF3] px-2.5 py-1.5 text-[0.6rem] font-medium text-[#6B7280] hover:bg-[#F4F7FA]"
                        >
                          <Eye className="h-3 w-3" />
                          View
                        </button>
                      </div>
                    </div>

                    {/* Artifacts Summary */}
                    <div className="mt-3 rounded-lg bg-gray-50 p-3">
                      <p className="mb-1.5 text-[0.6rem] font-medium text-[#6B7280]">Artifacts Summary</p>
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[0.55rem] text-[#6B7280]">
                        <div>
                          <span className="text-[#9CA3AF]">Workspace:</span>
                          <span className="ml-1 text-[#111827]">{report.artifacts_summary.workspace_id.slice(0, 12)}</span>
                        </div>
                        <div>
                          <span className="text-[#9CA3AF]">Sandbox:</span>
                          <span className="ml-1 text-[#111827]">{report.artifacts_summary.sandbox_id.slice(0, 12)}</span>
                        </div>
                        <div>
                          <span className="text-[#9CA3AF]">PR:</span>
                          <span className="ml-1 text-[#111827]">#{report.artifacts_summary.pr_number}</span>
                        </div>
                        <div>
                          <span className="text-[#9CA3AF]">Entities:</span>
                          <span className="ml-1 text-[#111827]">{report.artifacts_summary.code_intel_entities}</span>
                        </div>
                      </div>
                    </div>

                    {/* Stage Summary */}
                    {report.stage_summary.length > 0 && (
                      <div className="mt-3">
                        <p className="mb-1.5 text-[0.6rem] font-medium text-[#6B7280]">Stage Summary</p>
                        <div className="flex flex-wrap gap-1">
                          {report.stage_summary.map((s) => (
                            <span key={s.stage_index} className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[0.5rem] font-medium ${
                              s.status === "completed" ? "bg-green-50 text-green-600" :
                              s.status === "failed" ? "bg-red-50 text-red-600" :
                              s.status === "running" ? "bg-blue-50 text-blue-600" :
                              "bg-gray-100 text-gray-600"
                            }`}>
                              <StageIcon type={s.stage_type} />
                              {s.stage_type}
                              {s.error && <AlertTriangle className="h-2.5 w-2.5 text-red-500" />}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Recovery Log */}
                    {report.recovery_log.length > 0 && (
                      <div className="mt-3">
                        <p className="mb-1.5 text-[0.6rem] font-medium text-[#6B7280]">
                          Recovery Actions ({report.recovery_actions_taken.length})
                        </p>
                        <div className="space-y-1">
                          {report.recovery_log.map((entry, i) => (
                            <div key={i} className="flex items-center gap-2 text-[0.55rem] text-[#6B7280]">
                              <RotateCcw className="h-2.5 w-2.5 text-amber-500" />
                              <span className="capitalize font-medium text-[#111827]">{entry.action}</span>
                              <span className="text-[#9CA3AF]">stage {entry.stage_index} ({entry.stage_type})</span>
                              <span className="text-[#9CA3AF] truncate">— {entry.reason}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Delivery Summary */}
                    {report.artifacts_summary.delivery_summary && (
                      <div className="mt-3 text-[0.55rem] text-[#6B7280] p-2 rounded bg-gray-50">
                        <span className="font-medium text-[#111827]">Delivery: </span>
                        {report.artifacts_summary.delivery_summary}
                      </div>
                    )}
                  </motion.div>
                ))}
              </div>
            )}
          </motion.div>
        )}
      </div>
    </CortexShell>
  )
}
