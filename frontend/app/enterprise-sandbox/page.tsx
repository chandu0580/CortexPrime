"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import CortexShell from "@/components/layout/CortexShell"
import { stagger, variants } from "@/lib/motion-tokens"
import {
  useSandboxList,
  useSandbox,
  useSandboxLanguages,
  useCreateSandbox,
  usePrepareSandbox,
  useExecuteSandbox,
  usePauseSandbox,
  useResumeSandbox,
  useDestroySandbox,
  useSandboxArtifacts,
  useSandboxLogs,
  useSandboxResources,
} from "@/hooks/queries/enterprise/useEnterpriseSandbox"
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Box,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  Cpu,
  FileCode,
  FolderOpen,
  HardDrive,
  Loader2,
  MemoryStick,
  Play,
  Plus,
  Square,
  Terminal,
  Trash2,
  XCircle,
} from "lucide-react"
import { SUPPORTED_LANGUAGES, SANDBOX_STATUSES } from "@/types/sandbox"
import type { Sandbox } from "@/types/sandbox"

const STATUS_COLORS: Record<string, string> = {
  creating: "text-blue-500 bg-blue-50",
  ready: "text-[#38B88A] bg-[#F0FDF4]",
  running: "text-blue-500 bg-blue-50",
  paused: "text-amber-500 bg-amber-50",
  executing: "text-purple-500 bg-purple-50",
  completed: "text-[#38B88A] bg-[#F0FDF4]",
  failed: "text-red-500 bg-red-50",
  destroyed: "text-gray-400 bg-gray-100",
}

const LANG_ICONS: Record<string, any> = {
  python: FileCode,
  node: Terminal,
  java: Cpu,
  dotnet: Box,
  go: Terminal,
  rust: Cpu,
  shell: Terminal,
}

function CreateSandboxForm({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState("")
  const [repoUrl, setRepoUrl] = useState("")
  const [branch, setBranch] = useState("main")
  const [language, setLanguage] = useState("python")
  const createMutation = useCreateSandbox()

  const handleCreate = async () => {
    if (!name) return
    try {
      await createMutation.mutateAsync({ name, repo_url: repoUrl, branch, language })
      onClose()
    } catch (err) { console.error(err) }
  }

  return (
    <div className="rounded-xl border border-[#38B88A]/30 bg-[#F0FDF4] p-4">
      <h3 className="mb-3 text-sm font-bold text-[#111827]">Create Sandbox</h3>
      <div className="space-y-3">
        <input value={name} onChange={e => setName(e.target.value)} placeholder="Sandbox name"
          className="w-full rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] outline-none" />
        <div className="flex gap-2">
          <input value={repoUrl} onChange={e => setRepoUrl(e.target.value)} placeholder="Repo URL (optional)"
            className="flex-1 rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] outline-none" />
          <input value={branch} onChange={e => setBranch(e.target.value)} placeholder="Branch"
            className="w-28 rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] outline-none" />
        </div>
        <select value={language} onChange={e => setLanguage(e.target.value)}
          className="rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] outline-none">
          {SUPPORTED_LANGUAGES.map(l => <option key={l} value={l}>{l.charAt(0).toUpperCase() + l.slice(1)}</option>)}
        </select>
        <button onClick={handleCreate} disabled={!name || createMutation.isPending}
          className="w-full rounded-lg bg-[#38B88A] px-4 py-2 text-[0.72rem] font-bold text-white disabled:opacity-50">
          {createMutation.isPending ? <Loader2 className="inline h-3.5 w-3.5 animate-spin mr-1" /> : null}
          Create Sandbox
        </button>
      </div>
    </div>
  )
}

function SandboxDetailCard({
  sandbox,
  onClose,
}: {
  sandbox: Sandbox
  onClose: () => void
}) {
  const [command, setCommand] = useState("")
  const [execLang, setExecLang] = useState(sandbox.language)
  const [execResult, setExecResult] = useState<any>(null)

  const { data: artifacts } = useSandboxArtifacts(sandbox.sandbox_id)
  const { data: logs } = useSandboxLogs(sandbox.sandbox_id)
  const { data: resources } = useSandboxResources(sandbox.sandbox_id)

  const prepareMutation = usePrepareSandbox()
  const executeMutation = useExecuteSandbox()
  const pauseMutation = usePauseSandbox()
  const resumeMutation = useResumeSandbox()
  const destroyMutation = useDestroySandbox()

  const Icon = LANG_ICONS[sandbox.language] || Terminal

  const handlePrepare = async () => {
    try { await prepareMutation.mutateAsync(sandbox.sandbox_id) } catch (err) { console.error(err) }
  }

  const handleExecute = async () => {
    try {
      const result = await executeMutation.mutateAsync({
        id: sandbox.sandbox_id,
        command: command || undefined,
        language: execLang || undefined,
      })
      setExecResult(result)
    } catch (err) { console.error(err) }
  }

  const handlePause = async () => {
    try { await pauseMutation.mutateAsync(sandbox.sandbox_id) } catch (err) { console.error(err) }
  }

  const handleResume = async () => {
    try { await resumeMutation.mutateAsync(sandbox.sandbox_id) } catch (err) { console.error(err) }
  }

  const handleDestroy = async () => {
    try { await destroyMutation.mutateAsync(sandbox.sandbox_id); onClose() } catch (err) { console.error(err) }
  }

  return (
    <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
      {/* Header */}
      <div className="mb-4 flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-[#F4F7FA] p-2.5">
            <Icon className="h-4 w-4 text-[#6B7280]" />
          </div>
          <div>
            <h3 className="text-[0.9rem] font-bold text-[#111827]">{sandbox.name}</h3>
            <div className="flex flex-wrap items-center gap-2 text-[0.55rem] text-[#6B7280]">
              <span>{sandbox.sandbox_id}</span>
              <span>{sandbox.language}</span>
              <span>{sandbox.branch}</span>
              {sandbox.repo_url && <span className="max-w-[200px] truncate">{sandbox.repo_url}</span>}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1">
          {sandbox.status === "ready" && (
            <button onClick={handlePrepare} disabled={prepareMutation.isPending}
              className="rounded-lg px-2.5 py-1.5 text-[0.6rem] font-medium bg-blue-50 text-blue-600 hover:bg-blue-100">
              Prepare
            </button>
          )}
          {sandbox.status === "running" && (
            <button onClick={handlePause}
              className="rounded-lg px-2.5 py-1.5 text-[0.6rem] font-medium bg-amber-50 text-amber-600 hover:bg-amber-100">
              Pause
            </button>
          )}
          {sandbox.status === "paused" && (
            <button onClick={handleResume}
              className="rounded-lg px-2.5 py-1.5 text-[0.6rem] font-medium bg-blue-50 text-blue-600 hover:bg-blue-100">
              Resume
            </button>
          )}
          {sandbox.status !== "destroyed" && sandbox.status !== "creating" && (
            <button onClick={handleDestroy} disabled={destroyMutation.isPending}
              className="rounded-lg px-2.5 py-1.5 text-[0.6rem] font-medium bg-red-50 text-red-500 hover:bg-red-100">
              Destroy
            </button>
          )}
        </div>
      </div>

      {/* Status Badge */}
      <div className="mb-4 flex items-center gap-2">
        <span className={`rounded px-2 py-0.5 text-[0.55rem] font-medium ${STATUS_COLORS[sandbox.status] || "text-gray-500 bg-gray-100"}`}>
          {sandbox.status}
        </span>
        {sandbox.error && (
          <span className="flex items-center gap-1 text-[0.55rem] text-red-500">
            <AlertTriangle className="h-3 w-3" /> {sandbox.error.slice(0, 120)}
          </span>
        )}
      </div>

      {/* Resource Usage */}
      {resources && (
        <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            { icon: Cpu, label: "CPU", value: `${(resources as any).cpu_percent?.peak ?? "-"}%` },
            { icon: MemoryStick, label: "Memory", value: `${(resources as any).memory_mb?.end?.toFixed(1) ?? "-"} MB` },
            { icon: HardDrive, label: "Disk", value: `${(resources as any).disk_mb?.toFixed(1) ?? "-"} MB` },
            { icon: Clock, label: "Exec Time", value: `${((resources as any).total_execution_time_ms ?? 0).toFixed(0)} ms` },
          ].map((stat, i) => (
            <div key={i} className="flex items-center gap-2 rounded-lg bg-[#FAFBFC] px-2.5 py-2">
              <stat.icon className="h-3.5 w-3.5 text-[#6B7280]" />
              <div>
                <p className="text-[0.5rem] text-[#9CA3AF]">{stat.label}</p>
                <p className="text-[0.7rem] font-bold text-[#111827]">{stat.value}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Execute */}
      {sandbox.status !== "destroyed" && sandbox.status !== "creating" && (
        <div className="mb-4 rounded-lg border border-[#E8EDF3] p-3">
          <p className="mb-2 text-[0.65rem] font-medium text-[#111827]">Execute Command</p>
          <div className="flex gap-2">
            <input value={command} onChange={e => setCommand(e.target.value)} placeholder="Command (leave empty for default)"
              className="flex-1 rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.72rem] outline-none font-mono" />
            <select value={execLang} onChange={e => setExecLang(e.target.value)}
              className="rounded-lg border border-[#E8EDF3] px-2 py-2 text-[0.65rem] outline-none">
              {SUPPORTED_LANGUAGES.map(l => <option key={l} value={l}>{l}</option>)}
            </select>
            <button onClick={handleExecute} disabled={executeMutation.isPending}
              className="flex items-center gap-1.5 rounded-lg bg-[#38B88A] px-3 py-2 text-[0.65rem] font-bold text-white disabled:opacity-50">
              {executeMutation.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
              Run
            </button>
          </div>
        </div>
      )}

      {/* Execution Result */}
      {execResult && (
        <div className={`mb-4 rounded-lg border p-3 ${execResult.exit_code === 0 ? "border-[#38B88A]/30 bg-[#F0FDF4]" : "border-red-300 bg-red-50"}`}>
          <div className="flex items-center justify-between mb-1">
            <span className="text-[0.65rem] font-medium text-[#111827]">
              Exit Code: {execResult.exit_code} &middot; {execResult.duration_ms.toFixed(0)}ms
            </span>
            <span className={`text-[0.5rem] ${execResult.exit_code === 0 ? "text-[#38B88A]" : "text-red-500"}`}>
              {execResult.exit_code === 0 ? "SUCCESS" : "FAILED"}
            </span>
          </div>
          {execResult.stdout && (
            <pre className="max-h-24 overflow-auto rounded bg-white/60 p-2 text-[0.55rem] text-[#6B7280] font-mono">{execResult.stdout.slice(0, 1000)}</pre>
          )}
          {execResult.stderr && (
            <pre className="mt-1 max-h-24 overflow-auto rounded bg-red-50/60 p-2 text-[0.55rem] text-red-500 font-mono">{execResult.stderr.slice(0, 1000)}</pre>
          )}
        </div>
      )}

      {/* Artifacts */}
      <div className="mb-4">
        <h4 className="mb-1.5 text-[0.65rem] font-medium text-[#111827]">Artifacts ({artifacts?.artifacts?.length ?? 0})</h4>
        {artifacts?.artifacts && artifacts.artifacts.length > 0 ? (
          <div className="space-y-1">
            {artifacts.artifacts.slice(0, 8).map((a: any, i: number) => (
              <div key={i} className="flex items-center justify-between rounded-lg bg-[#FAFBFC] px-2.5 py-1.5">
                <div className="flex items-center gap-2">
                  <FolderOpen className="h-3 w-3 text-[#6B7280]" />
                  <span className="text-[0.6rem] text-[#111827]">{a.name}</span>
                </div>
                <span className="text-[0.5rem] text-[#9CA3AF]">
                  {a.type} &middot; {(a.size_bytes / 1024).toFixed(1)} KB
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-[0.55rem] text-[#9CA3AF]">No artifacts yet.</p>
        )}
      </div>

      {/* Logs */}
      <div>
        <h4 className="mb-1.5 text-[0.65rem] font-medium text-[#111827]">Logs ({logs?.logs?.length ?? 0})</h4>
        {logs?.logs && logs.logs.length > 0 ? (
          <div className="max-h-32 space-y-1 overflow-auto">
            {logs.logs.slice(-10).reverse().map((l: any, i: number) => (
              <div key={i} className="flex items-start gap-2 text-[0.55rem]">
                <span className={`shrink-0 rounded px-1 py-0.5 font-medium ${
                  l.type === "execution" ? "bg-purple-50 text-purple-500" :
                  l.type === "repo_prep" ? "bg-blue-50 text-blue-500" :
                  l.type === "dependencies" ? "bg-amber-50 text-amber-500" :
                  "bg-gray-50 text-gray-500"
                }`}>
                  {l.type}
                </span>
                <span className="text-[#6B7280]">{l.message.slice(0, 160)}</span>
                {l.exit_code !== undefined && (
                  <span className={`shrink-0 font-mono ${l.exit_code === 0 ? "text-[#38B88A]" : "text-red-500"}`}>
                    [{l.exit_code}]
                  </span>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-[0.55rem] text-[#9CA3AF]">No logs yet.</p>
        )}
      </div>
    </div>
  )
}

function SandboxCard({ sandbox, onSelect }: { sandbox: Sandbox; onSelect: () => void }) {
  const Icon = LANG_ICONS[sandbox.language] || Terminal
  const hasError = sandbox.status === "failed"
  const isCompleted = sandbox.status === "completed"
  const isDestroyed = sandbox.status === "destroyed"

  return (
    <motion.div
      variants={variants.fadeUp}
      onClick={onSelect}
      className={`cursor-pointer rounded-xl border p-4 transition-all hover:shadow-sm ${
        hasError ? "border-red-300 bg-red-50" :
        isCompleted ? "border-[#38B88A]/30 bg-[#F0FDF4]" :
        isDestroyed ? "border-gray-200 bg-gray-50" :
        "border-[#E8EDF3] bg-white"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className={`rounded-lg p-2 ${
            hasError ? "bg-red-100" : isCompleted ? "bg-[#38B88A]/10" : "bg-[#F4F7FA]"
          }`}>
            <Icon className={`h-4 w-4 ${hasError ? "text-red-500" : isCompleted ? "text-[#38B88A]" : "text-[#6B7280]"}`} />
          </div>
          <div className="min-w-0">
            <p className="text-[0.78rem] font-bold text-[#111827]">{sandbox.name}</p>
            <div className="flex flex-wrap items-center gap-1.5 mt-0.5">
              <span className={`rounded px-1.5 py-0.5 text-[0.45rem] font-medium ${STATUS_COLORS[sandbox.status] || "text-gray-500 bg-gray-100"}`}>
                {sandbox.status}
              </span>
              <span className="text-[0.5rem] text-[#9CA3AF]">{sandbox.language}</span>
              <span className="text-[0.5rem] text-[#9CA3AF]">{sandbox.executions.length} exec</span>
            </div>
          </div>
        </div>
        <div className="shrink-0 text-right">
          <p className="text-[0.5rem] text-[#9CA3AF]">{new Date(sandbox.created_at).toLocaleDateString()}</p>
          <p className="text-[0.45rem] text-[#9CA3AF]">{sandbox.artifacts.length} artifacts</p>
        </div>
      </div>
    </motion.div>
  )
}

export default function EnterpriseSandboxCenter() {
  const [activeTab, setActiveTab] = useState("sandboxes")
  const [showCreate, setShowCreate] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState("")
  const [langFilter, setLangFilter] = useState("")

  const { data: sandboxes } = useSandboxList(statusFilter, langFilter)
  const { data: languages } = useSandboxLanguages()
  const selectedSandbox = useSandbox(selectedId || "")

  const tabs = [
    { id: "sandboxes", label: "Sandboxes", icon: Box },
    { id: "running", label: "Running", icon: Activity },
    { id: "completed", label: "Completed", icon: CheckCircle2 },
  ]

  return (
    <CortexShell title="Execution Sandbox" subtitle="Isolated, reproducible engineering environments for every mission">
      <div className="relative z-10 mx-auto max-w-7xl space-y-6">

        {/* Tabs */}
        <div className="flex items-center gap-2 border-b border-[#E8EDF3] pb-2">
          {tabs.map(tab => {
            const Icon = tab.icon
            const isActive = activeTab === tab.id
            return (
              <button key={tab.id} onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-[0.65rem] font-medium rounded-lg transition-colors ${
                  isActive ? "bg-[#38B88A]/10 text-[#38B88A]" : "text-[#6B7280] hover:text-[#111827]"
                }`}>
                <Icon className="h-3.5 w-3.5" />
                {tab.label}
              </button>
            )
          })}
          <div className="flex-1" />
          {selectedId ? (
            <button onClick={() => { setSelectedId(null) }}
              className="flex items-center gap-1 rounded-lg border border-[#E8EDF3] px-2.5 py-1.5 text-[0.6rem] text-[#6B7280] hover:bg-[#F4F7FA]">
              <BarChart3 className="h-3 w-3" /> All Sandboxes
            </button>
          ) : (
            <button onClick={() => setShowCreate(!showCreate)}
              className="flex items-center gap-1.5 rounded-lg border border-[#38B88A]/30 px-3 py-1.5 text-[0.65rem] font-medium text-[#38B88A] hover:bg-[#F0FDF4]">
              {showCreate ? <XCircle className="h-3.5 w-3.5" /> : <Plus className="h-3.5 w-3.5" />}
              {showCreate ? "Cancel" : "New Sandbox"}
            </button>
          )}
        </div>

        {/* Filters */}
        {!selectedId && (
          <div className="flex flex-wrap items-center gap-2">
            <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
              className="rounded-lg border border-[#E8EDF3] px-2.5 py-1.5 text-[0.65rem] outline-none">
              <option value="">All Statuses</option>
              {SANDBOX_STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
            <select value={langFilter} onChange={e => setLangFilter(e.target.value)}
              className="rounded-lg border border-[#E8EDF3] px-2.5 py-1.5 text-[0.65rem] outline-none">
              <option value="">All Languages</option>
              {SUPPORTED_LANGUAGES.map(l => <option key={l} value={l}>{l}</option>)}
            </select>
          </div>
        )}

        {/* Create Form */}
        {!selectedId && showCreate && <CreateSandboxForm onClose={() => setShowCreate(false)} />}

        {/* Main Content */}
        {selectedId && selectedSandbox.data ? (
          <SandboxDetailCard sandbox={selectedSandbox.data} onClose={() => setSelectedId(null)} />
        ) : (
          <motion.div initial="hidden" animate="visible" variants={stagger(0.03, 0.01)}>
            {activeTab === "sandboxes" && (
              <div className="space-y-2">
                {sandboxes && sandboxes.length > 0 ? (
                  sandboxes.map(s => (
                    <SandboxCard key={s.sandbox_id} sandbox={s} onSelect={() => setSelectedId(s.sandbox_id)} />
                  ))
                ) : (
                  <div className="flex flex-col items-center rounded-xl border border-[#E8EDF3] bg-white py-16 text-[#9CA3AF]">
                    <Box className="mb-3 h-10 w-10 opacity-30" />
                    <p className="text-sm">No sandboxes yet. Create one to get started.</p>
                  </div>
                )}
              </div>
            )}
            {activeTab === "running" && (
              <div className="space-y-2">
                {sandboxes?.filter(s => s.status === "running" || s.status === "executing").map(s => (
                  <SandboxCard key={s.sandbox_id} sandbox={s} onSelect={() => setSelectedId(s.sandbox_id)} />
                ))}
                {(!sandboxes || sandboxes.filter(s => s.status === "running" || s.status === "executing").length === 0) && (
                  <div className="flex flex-col items-center rounded-xl border border-[#E8EDF3] bg-white py-16 text-[#9CA3AF]">
                    <Activity className="mb-3 h-10 w-10 opacity-30" />
                    <p className="text-sm">No running sandboxes.</p>
                  </div>
                )}
              </div>
            )}
            {activeTab === "completed" && (
              <div className="space-y-2">
                {sandboxes?.filter(s => s.status === "completed").map(s => (
                  <SandboxCard key={s.sandbox_id} sandbox={s} onSelect={() => setSelectedId(s.sandbox_id)} />
                ))}
                {(!sandboxes || sandboxes.filter(s => s.status === "completed").length === 0) && (
                  <div className="flex flex-col items-center rounded-xl border border-[#E8EDF3] bg-white py-16 text-[#9CA3AF]">
                    <CheckCircle2 className="mb-3 h-10 w-10 opacity-30" />
                    <p className="text-sm">No completed sandboxes.</p>
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
