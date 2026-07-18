"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  GitMerge, Play, Pause, XCircle, Trash2, Plus, RefreshCw,
  Activity, CheckCircle, Clock, AlertTriangle, Loader2,
} from "lucide-react"
import { usePipelineList, usePipelineDashboard, useStartPipeline, usePausePipeline, useResumePipeline, useCancelPipeline, useDeletePipeline, useCreatePipeline, usePatchToPr } from "@/hooks/queries/enterprise/useEnterprisePipeline"
import type { PipelineRun, PipelineStage } from "@/types/pipeline"

const STAGE_LABELS: Record<PipelineStage, string> = {
  trigger: "Trigger",
  sandbox: "Sandbox",
  code_intel: "Code Intel",
  patch: "Patch Pipeline",
  git: "Git Ops",
  approval: "Approval",
  complete: "Complete",
}

const STATUS_ICONS: Record<string, React.ReactNode> = {
  pending: <Clock className="w-4 h-4 text-yellow-400" />,
  running: <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />,
  paused: <Pause className="w-4 h-4 text-orange-400" />,
  completed: <CheckCircle className="w-4 h-4 text-green-400" />,
  failed: <XCircle className="w-4 h-4 text-red-400" />,
  cancelled: <XCircle className="w-4 h-4 text-gray-400" />,
}

function PipelineStageBadge({ stage, pipeline }: { stage: PipelineStage; pipeline: PipelineRun }) {
  const completed = pipeline.stages_completed?.includes(stage) ?? false
  const failed = pipeline.stages_failed?.includes(stage) ?? false
  const current = pipeline.current_stage === stage

  let color = "bg-gray-800 text-gray-400"
  if (completed) color = "bg-green-900/40 text-green-300"
  if (failed) color = "bg-red-900/40 text-red-300"
  if (current) color = "bg-blue-900/40 text-blue-300 ring-1 ring-blue-500"

  return (
    <span className={`px-2 py-0.5 rounded text-xs font-mono ${color}`}>
      {STAGE_LABELS[stage]}
      {current && " ←"}
    </span>
  )
}

function PipelineCard({ pipeline, onAction }: { pipeline: PipelineRun; onAction: () => void }) {
  const startPipe = useStartPipeline()
  const pausePipe = usePausePipeline()
  const resumePipe = useResumePipeline()
  const cancelPipe = useCancelPipeline()
  const deletePipe = useDeletePipeline()

  const handle = async (fn: () => Promise<unknown>) => {
    try {
      await fn()
      onAction()
    } catch { /* ignore */ }
  }

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-gray-900 border border-gray-700 rounded-lg p-4 space-y-3"
    >
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            {STATUS_ICONS[pipeline.status] ?? <Activity className="w-4 h-4" />}
            <span className="font-semibold text-sm">{pipeline.name}</span>
          </div>
          {pipeline.description && (
            <p className="text-xs text-gray-500 mt-1">{pipeline.description}</p>
          )}
        </div>
        <span className="text-xs text-gray-500 font-mono">{pipeline.pipeline_id.slice(0, 16)}</span>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {(["trigger", "sandbox", "code_intel", "patch", "git", "approval", "complete"] as PipelineStage[]).map((s) => (
          <PipelineStageBadge key={s} stage={s} pipeline={pipeline} />
        ))}
      </div>

      <div className="flex items-center justify-between pt-1">
        <span className="text-xs text-gray-500">
          {pipeline.created_at ? new Date(pipeline.created_at).toLocaleString() : ""}
        </span>
        <div className="flex gap-1">
          {pipeline.status === "pending" && (
            <button onClick={() => handle(() => startPipe.mutateAsync(pipeline.pipeline_id))} className="p-1 rounded hover:bg-gray-700 text-blue-400" title="Start">
              <Play className="w-4 h-4" />
            </button>
          )}
          {pipeline.status === "running" && (
            <>
              <button onClick={() => handle(() => pausePipe.mutateAsync(pipeline.pipeline_id))} className="p-1 rounded hover:bg-gray-700 text-orange-400" title="Pause">
                <Pause className="w-4 h-4" />
              </button>
              <button onClick={() => handle(() => cancelPipe.mutateAsync(pipeline.pipeline_id))} className="p-1 rounded hover:bg-gray-700 text-red-400" title="Cancel">
                <XCircle className="w-4 h-4" />
              </button>
            </>
          )}
          {pipeline.status === "paused" && (
            <button onClick={() => handle(() => resumePipe.mutateAsync(pipeline.pipeline_id))} className="p-1 rounded hover:bg-gray-700 text-green-400" title="Resume">
              <Play className="w-4 h-4" />
            </button>
          )}
          {["completed", "failed", "cancelled"].includes(pipeline.status) && (
            <button onClick={() => handle(() => deletePipe.mutateAsync(pipeline.pipeline_id))} className="p-1 rounded hover:bg-gray-700 text-gray-500" title="Delete">
              <Trash2 className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {pipeline.error && (
        <div className="bg-red-900/20 border border-red-800 rounded p-2 text-xs text-red-300">
          {pipeline.error}
        </div>
      )}
    </motion.div>
  )
}

export default function EnterprisePipelinePage() {
  const [showCreate, setShowCreate] = useState(false)
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [repoUrl, setRepoUrl] = useState("")
  const [tab, setTab] = useState<"all" | "running" | "completed" | "failed">("all")

  const { data: pipelines = [], refetch } = usePipelineList(tab === "all" ? "" : tab)
  const { data: dashboard } = usePipelineDashboard()
  const createPipe = useCreatePipeline()

  const handleCreate = async () => {
    try {
      await createPipe.mutateAsync({ name, description, repo_url: repoUrl })
      setName("")
      setDescription("")
      setRepoUrl("")
      setShowCreate(false)
      refetch()
    } catch { /* ignore */ }
  }

  const filtered = tab === "all" ? pipelines : pipelines.filter((p) => p.status === tab)

  return (
    <div className="min-h-screen bg-black text-gray-100 p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <GitMerge className="w-7 h-7 text-purple-400" />
            <h1 className="text-2xl font-bold">AI Pipeline Orchestrator</h1>
          </div>
          <div className="flex gap-2">
            <button onClick={() => refetch()} className="p-2 rounded-lg bg-gray-800 hover:bg-gray-700 border border-gray-700">
              <RefreshCw className="w-4 h-4" />
            </button>
            <button onClick={() => setShowCreate(!showCreate)} className="flex items-center gap-2 px-4 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 text-white font-medium">
              <Plus className="w-4 h-4" /> New Pipeline
            </button>
          </div>
        </div>

        {/* Dashboard Stats */}
        {dashboard && (
          <div className="grid grid-cols-5 gap-3">
            {[
              { label: "Total", value: dashboard.total_pipelines, color: "text-blue-400" },
              { label: "Running", value: dashboard.running, color: "text-blue-300" },
              { label: "Completed", value: dashboard.completed, color: "text-green-400" },
              { label: "Failed", value: dashboard.failed, color: "text-red-400" },
              { label: "Pending", value: dashboard.by_status?.pending ?? 0, color: "text-yellow-400" },
            ].map((s) => (
              <div key={s.label} className="bg-gray-900 border border-gray-700 rounded-lg p-3 text-center">
                <div className={`text-2xl font-bold ${s.color}`}>{s.value}</div>
                <div className="text-xs text-gray-500">{s.label}</div>
              </div>
            ))}
          </div>
        )}

        {/* Create Form */}
        <AnimatePresence>
          {showCreate && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="bg-gray-900 border border-gray-700 rounded-lg p-4 space-y-3 overflow-hidden"
            >
              <h2 className="text-sm font-semibold">Create Pipeline</h2>
              <input
                value={name} onChange={(e) => setName(e.target.value)}
                placeholder="Pipeline name"
                className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm"
              />
              <input
                value={description} onChange={(e) => setDescription(e.target.value)}
                placeholder="Description (optional)"
                className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm"
              />
              <input
                value={repoUrl} onChange={(e) => setRepoUrl(e.target.value)}
                placeholder="Repo URL (optional)"
                className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm"
              />
              <div className="flex gap-2">
                <button onClick={handleCreate} className="px-4 py-2 rounded bg-purple-600 hover:bg-purple-500 text-sm font-medium">
                  Create & Start
                </button>
                <button onClick={() => setShowCreate(false)} className="px-4 py-2 rounded bg-gray-700 hover:bg-gray-600 text-sm">
                  Cancel
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Tabs */}
        <div className="flex gap-2 border-b border-gray-800 pb-2">
          {(["all", "running", "completed", "failed"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-3 py-1 rounded text-sm font-medium ${
                tab === t ? "bg-purple-600 text-white" : "text-gray-400 hover:text-white"
              }`}
            >
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>

        {/* Pipeline List */}
        <div className="space-y-3">
          {filtered.length === 0 && (
            <div className="text-center text-gray-600 py-12">
              <GitMerge className="w-12 h-12 mx-auto mb-3 opacity-40" />
              <p className="text-lg font-medium">No pipelines found</p>
              <p className="text-sm">Create a new pipeline to get started</p>
            </div>
          )}
          <AnimatePresence>
            {filtered.map((p) => (
              <PipelineCard key={p.pipeline_id} pipeline={p} onAction={() => refetch()} />
            ))}
          </AnimatePresence>
        </div>
      </div>
    </div>
  )
}
