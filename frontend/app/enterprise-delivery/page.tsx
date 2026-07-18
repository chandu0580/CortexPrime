"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import CortexShell from "@/components/layout/CortexShell"
import { stagger, variants } from "@/lib/motion-tokens"
import {
  useDeliveryList,
  useDeliveryDetail,
  useDeliveryTimeline,
  useDeliveryArtifacts,
  useDeliveryStats,
  useStartDelivery,
  usePauseDelivery,
  useResumeDelivery,
  useCancelDelivery,
  useRollbackDelivery,
} from "@/hooks/queries/enterprise/useEnterpriseDelivery"
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  Download,
  FolderOpen,
  GitBranch,
  Hammer,
  Loader2,
  Pause,
  Play,
  Plus,
  RotateCcw,
  Shield,
  Square,
  StepForward,
  Terminal,
  XCircle,
  Eye,
  RefreshCw,
  BarChart3,
  FileText,
  ShieldCheck,
  ThumbsUp,
} from "lucide-react"

const STATE_COLORS: Record<string, string> = {
  pending: "bg-gray-100 text-gray-600",
  queued: "bg-blue-50 text-blue-600",
  running: "bg-blue-50 text-blue-600",
  waiting_approval: "bg-amber-50 text-amber-600",
  paused: "bg-purple-50 text-purple-600",
  retrying: "bg-orange-50 text-orange-600",
  completed: "bg-[#F0FDF4] text-[#38B88A]",
  failed: "bg-red-50 text-red-600",
  cancelled: "bg-gray-100 text-gray-500",
  rolled_back: "bg-amber-50 text-amber-600",
  resumed: "bg-green-50 text-green-600",
}

const STAGE_LABELS: Record<string, string> = {
  repository: "Repository",
  workspace: "Workspace",
  patch: "Patch",
  build: "Build",
  qa: "QA",
  security: "Security",
  approval: "Approval",
  pr: "PR",
  deployment: "Deployment",
  verification: "Verification",
  monitoring: "Monitoring",
  learning: "Learning",
}

const STAGE_ICONS: Record<string, React.ElementType> = {
  repository: GitBranch,
  workspace: FolderOpen,
  patch: FileText,
  build: Hammer,
  qa: CheckCircle2,
  security: ShieldCheck,
  approval: ThumbsUp,
  pr: GitBranch,
  deployment: Terminal,
  verification: Eye,
  monitoring: Activity,
  learning: BarChart3,
}

const DELIVERY_STAGES = [
  "repository", "workspace", "patch", "build", "qa",
  "security", "approval", "pr", "deployment", "verification",
  "monitoring", "learning",
]

function StateBadge({ state }: { state: string }) {
  return (
    <span className={`rounded-full px-2 py-0.5 text-[0.55rem] font-medium capitalize ${STATE_COLORS[state] || "bg-gray-100 text-gray-600"}`}>
      {state.replace(/_/g, " ")}
    </span>
  )
}

function StagePipeline({ current, completed, failed, timeline }: {
  current: string
  completed: string[]
  failed: string[]
  timeline: { stage: string; status: string; timestamp: string }[]
}) {
  return (
    <div className="overflow-x-auto pb-2">
      <div className="flex items-center gap-1 min-w-max">
        {DELIVERY_STAGES.map((stage, i) => {
          const Icon = STAGE_ICONS[stage] || Activity
          const isCurrent = stage === current
          const isCompleted = completed.includes(stage)
          const isFailed = failed.includes(stage)
          const stageEntry = timeline?.find(t => t.stage === stage)
          const ts = stageEntry?.timestamp ? new Date(stageEntry.timestamp).toLocaleTimeString() : ""

          return (
            <div key={stage} className="flex items-center">
              <div className="flex flex-col items-center">
                <div
                  className={`flex items-center justify-center w-8 h-8 rounded-full border-2 transition-all ${
                    isCurrent
                      ? "border-[#38B88A] bg-[#F0FDF4] text-[#38B88A] scale-110 shadow-md"
                      : isCompleted
                      ? "border-[#38B88A] bg-[#F0FDF4] text-[#38B88A]"
                      : isFailed
                      ? "border-red-400 bg-red-50 text-red-500"
                      : "border-gray-200 bg-white text-gray-400"
                  }`}
                >
                  {isCurrent ? (
                    <Loader2 size={14} className="animate-spin" />
                  ) : isCompleted ? (
                    <CheckCircle2 size={14} />
                  ) : isFailed ? (
                    <XCircle size={14} />
                  ) : (
                    <Icon size={14} />
                  )}
                </div>
                <span className={`text-[0.5rem] mt-1 font-medium ${
                  isCurrent ? "text-[#38B88A]" : isCompleted ? "text-[#38B88A]" : isFailed ? "text-red-500" : "text-gray-400"
                }`}>
                  {STAGE_LABELS[stage]}
                </span>
                {ts && (
                  <span className="text-[0.4rem] text-gray-400 mt-0.5">{ts}</span>
                )}
              </div>
              {i < DELIVERY_STAGES.length - 1 && (
                <div className={`w-3 h-0.5 mx-0.5 ${
                  isCompleted ? "bg-[#38B88A]" : "bg-gray-200"
                }`} />
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function TimelineView({ entries }: { entries: { stage: string; status: string; message: string; timestamp: string }[] }) {
  return (
    <div className="space-y-1 max-h-60 overflow-y-auto">
      {entries.length === 0 && (
        <p className="text-xs text-gray-400 text-center py-4">No timeline entries</p>
      )}
      {entries.map((entry, i) => (
        <div key={i} className="flex items-start gap-2 text-xs">
          <div className={`w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 ${
            entry.status === "completed" ? "bg-[#38B88A]"
            : entry.status === "failed" ? "bg-red-500"
            : entry.status === "running" ? "bg-blue-500"
            : entry.status === "paused" || entry.status === "cancelled" ? "bg-gray-400"
            : "bg-amber-500"
          }`} />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1">
              <span className="font-medium text-gray-700 capitalize">{entry.stage}</span>
              <span className={`capitalize ${
                entry.status === "completed" ? "text-[#38B88A]"
                : entry.status === "failed" ? "text-red-500"
                : "text-gray-500"
              }`}>
                {entry.status}
              </span>
              {entry.timestamp && (
                <span className="text-gray-400 ml-auto">
                  {new Date(entry.timestamp).toLocaleTimeString()}
                </span>
              )}
            </div>
            {entry.message && (
              <p className="text-gray-500 truncate">{entry.message}</p>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

function DeliveryCard({ delivery, onSelect }: { delivery: Record<string, unknown>; onSelect: (id: string) => void }) {
  const d = delivery as { delivery_id: string; state: string; current_stage: string; stages_completed: string[]; stages_failed: string[]; mission: string; created_at: string }
  const d2 = delivery as { blueprint?: { mission?: string }; created_at: string }
  const mission = (delivery as any).blueprint?.mission || d.mission || "Unknown"
  return (
    <motion.div
      variants={variants}
      className="rounded-lg p-3 cursor-pointer hover:shadow-md transition-shadow"
      style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
      onClick={() => onSelect(d.delivery_id)}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-mono text-gray-400">{d.delivery_id?.slice(0, 16)}...</span>
        <StateBadge state={d.state} />
      </div>
      <p className="text-sm font-semibold truncate" style={{ color: "var(--text-primary)" }}>
        {mission}
      </p>
      <div className="flex items-center gap-2 mt-1 text-xs text-gray-500">
        {d.current_stage && (
          <span className="flex items-center gap-1">
            <Activity size={10} />
            {d.current_stage}
          </span>
        )}
        <span className="flex items-center gap-1">
          <CheckCircle2 size={10} className="text-[#38B88A]" />
          {d.stages_completed?.length || 0}
        </span>
        {(d.stages_failed?.length || 0) > 0 && (
          <span className="flex items-center gap-1">
            <XCircle size={10} className="text-red-500" />
            {d.stages_failed?.length}
          </span>
        )}
      </div>
      <p className="text-[0.6rem] text-gray-400 mt-1">
        {new Date(d2.created_at).toLocaleString()}
      </p>
    </motion.div>
  )
}

export default function EnterpriseDeliveryCenter() {
  const [activeTab, setActiveTab] = useState<string>("pipeline")
  const [selectedId, setSelectedId] = useState<string>("")
  const [showCreate, setShowCreate] = useState(false)
  const [newMission, setNewMission] = useState("")
  const [newRepo, setNewRepo] = useState("")

  const { data: deliveries, isLoading } = useDeliveryList()
  const { data: detail } = useDeliveryDetail(selectedId)
  const { data: timeline } = useDeliveryTimeline(selectedId)
  const { data: artifacts } = useDeliveryArtifacts(selectedId)
  const { data: stats } = useDeliveryStats()

  const startMutation = useStartDelivery()
  const pauseMutation = usePauseDelivery()
  const resumeMutation = useResumeDelivery()
  const cancelMutation = useCancelDelivery()
  const rollbackMutation = useRollbackDelivery()

  const handleCreate = async () => {
    if (!newMission || !newRepo) return
    try {
      await startMutation.mutateAsync({ mission: newMission, repository: newRepo })
      setNewMission("")
      setNewRepo("")
      setShowCreate(false)
    } catch (e) {
      console.error("Failed to start delivery", e)
    }
  }

  const handleAction = async (action: string) => {
    if (!selectedId) return
    try {
      if (action === "pause") await pauseMutation.mutateAsync(selectedId)
      else if (action === "resume") await resumeMutation.mutateAsync(selectedId)
      else if (action === "cancel") await cancelMutation.mutateAsync(selectedId)
      else if (action === "rollback") await rollbackMutation.mutateAsync(selectedId)
    } catch (e) {
      console.error(`Failed to ${action} delivery`, e)
    }
  }

  const selected = detail as Record<string, any> | undefined
  const blueprint = selected?.blueprint || {}
  const timelineEntries = timeline?.timeline || []
  const artifactList = artifacts?.artifacts || []
  const statsData = stats as Record<string, any> | undefined

  return (
    <CortexShell>
      <motion.div variants={variants.fadeUp} initial="initial" animate="animate" className="p-6 space-y-6">
        {/* Header */}
        <motion.div variants={variants} className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>Enterprise Delivery Center</h1>
            <p className="text-sm text-gray-500">Coordinate the complete software delivery lifecycle</p>
          </div>
          <div className="flex items-center gap-2">
            {statsData && (
              <div className="flex items-center gap-3 text-xs text-gray-500 mr-4">
                <span>{statsData.total_deliveries || 0} total</span>
                <span className="text-[#38B88A]">{statsData.completed || 0} done</span>
                {(statsData.failed || 0) > 0 && <span className="text-red-500">{statsData.failed} failed</span>}
              </div>
            )}
            <button
              onClick={() => setShowCreate(!showCreate)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-white"
              style={{ background: "var(--accent-primary)" }}
            >
              <Plus size={14} />
              New Delivery
            </button>
          </div>
        </motion.div>

        {/* Create Form */}
        {showCreate && (
          <motion.div
            variants={variants}
            className="rounded-lg p-4 space-y-3"
            style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
          >
            <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Start New Delivery</h3>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-gray-500 block mb-1">Mission / Version</label>
                <input
                  value={newMission}
                  onChange={(e) => setNewMission(e.target.value)}
                  placeholder="e.g. release-3.2.0"
                  className="w-full px-2 py-1.5 rounded-lg text-xs border"
                  style={{ background: "var(--bg)", borderColor: "var(--border)", color: "var(--text-primary)" }}
                />
              </div>
              <div>
                <label className="text-xs text-gray-500 block mb-1">Repository URL</label>
                <input
                  value={newRepo}
                  onChange={(e) => setNewRepo(e.target.value)}
                  placeholder="https://github.com/org/repo"
                  className="w-full px-2 py-1.5 rounded-lg text-xs border"
                  style={{ background: "var(--bg)", borderColor: "var(--border)", color: "var(--text-primary)" }}
                />
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowCreate(false)}
                className="px-3 py-1.5 rounded-lg text-xs font-medium border"
                style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={!newMission || !newRepo || startMutation.isPending}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium text-white disabled:opacity-50"
                style={{ background: "var(--accent-primary)" }}
              >
                {startMutation.isPending ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
                Start Delivery
              </button>
            </div>
          </motion.div>
        )}

        {/* Main Layout */}
        <div className="grid grid-cols-12 gap-4">
          {/* Delivery List */}
          <div className="col-span-4 space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Deliveries</h2>
              <div className="flex gap-1">
                {["all", "running", "completed", "failed"].map((f) => (
                  <button
                    key={f}
                    onClick={() => setActiveTab(f === "all" ? "pipeline" : f)}
                    className={`px-2 py-0.5 rounded text-[0.55rem] font-medium capitalize ${
                      activeTab === (f === "all" ? "pipeline" : f)
                        ? "text-white"
                        : "text-gray-500"
                    }`}
                    style={activeTab === (f === "all" ? "pipeline" : f) ? { background: "var(--accent-primary)" } : {}}
                  >
                    {f}
                  </button>
                ))}
              </div>
            </div>
            <div className="space-y-2 max-h-[70vh] overflow-y-auto pr-1">
              {isLoading && (
                <div className="flex items-center justify-center py-8">
                  <Loader2 size={20} className="animate-spin text-gray-400" />
                </div>
              )}
              {!isLoading && (!deliveries || deliveries.length === 0) && (
                <p className="text-xs text-gray-400 text-center py-8">No deliveries yet</p>
              )}
              {deliveries?.map((d) => (
                <DeliveryCard
                  key={d.delivery_id}
                  delivery={d as unknown as Record<string, unknown>}
                  onSelect={setSelectedId}
                />
              ))}
            </div>
          </div>

          {/* Detail Panel */}
          <div className="col-span-8 space-y-4">
            {!selectedId && (
              <motion.div
                variants={variants}
                className="rounded-lg p-8 flex flex-col items-center justify-center"
                style={{ background: "var(--surface)", border: "1px solid var(--border)", minHeight: "400px" }}
              >
                <Activity size={40} className="text-gray-300 mb-3" />
                <p className="text-sm text-gray-400">Select a delivery to view details</p>
              </motion.div>
            )}

            {selectedId && selected && (
              <>
                {/* Delivery Header */}
                <motion.div
                  variants={variants}
                  className="rounded-lg p-4"
                  style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
                >
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                        {blueprint?.mission || selected.delivery_id?.slice(0, 16)}
                      </h2>
                      <StateBadge state={selected.state} />
                    </div>
                    <div className="flex items-center gap-1.5">
                      {selected.state === "running" && (
                        <button onClick={() => handleAction("pause")}
                          className="flex items-center gap-1 px-2 py-1 rounded text-[0.6rem] font-medium text-purple-600 bg-purple-50">
                          <Pause size={10} /> Pause
                        </button>
                      )}
                      {selected.state === "paused" && (
                        <button onClick={() => handleAction("resume")}
                          className="flex items-center gap-1 px-2 py-1 rounded text-[0.6rem] font-medium text-green-600 bg-green-50">
                          <Play size={10} /> Resume
                        </button>
                      )}
                      {["running", "paused", "queued", "waiting_approval"].includes(selected.state) && (
                        <button onClick={() => handleAction("cancel")}
                          className="flex items-center gap-1 px-2 py-1 rounded text-[0.6rem] font-medium text-gray-600 bg-gray-100">
                          <Square size={10} /> Cancel
                        </button>
                      )}
                      {["completed", "failed"].includes(selected.state) && (
                        <button onClick={() => handleAction("rollback")}
                          className="flex items-center gap-1 px-2 py-1 rounded text-[0.6rem] font-medium text-amber-600 bg-amber-50">
                          <RotateCcw size={10} /> Rollback
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Stage Pipeline */}
                  <StagePipeline
                    current={selected.current_stage}
                    completed={selected.stages_completed || []}
                    failed={selected.stages_failed || []}
                    timeline={timelineEntries}
                  />

                  <div className="grid grid-cols-4 gap-3 mt-3">
                    <div className="text-xs">
                      <span className="text-gray-400">Delivery ID</span>
                      <p className="font-mono font-medium" style={{ color: "var(--text-primary)" }}>
                        {selected.delivery_id?.slice(0, 20)}
                      </p>
                    </div>
                    <div className="text-xs">
                      <span className="text-gray-400">Created</span>
                      <p style={{ color: "var(--text-primary)" }}>
                        {selected.created_at ? new Date(selected.created_at).toLocaleString() : "-"}
                      </p>
                    </div>
                    <div className="text-xs">
                      <span className="text-gray-400">Completed</span>
                      <p style={{ color: "var(--text-primary)" }}>
                        {selected.completed_at ? new Date(selected.completed_at).toLocaleString() : "-"}
                      </p>
                    </div>
                    <div className="text-xs">
                      <span className="text-gray-400">Repository</span>
                      <p className="truncate" style={{ color: "var(--text-primary)" }}>
                        {blueprint?.repository || "-"}
                      </p>
                    </div>
                  </div>
                </motion.div>

                {/* Tabs: Timeline, Artifacts, Blueprint, State Machine */}
                <motion.div
                  variants={variants}
                  className="rounded-lg"
                  style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
                >
                  <div className="flex border-b" style={{ borderColor: "var(--border)" }}>
                    {[
                      { key: "timeline", label: "Timeline", icon: Clock },
                      { key: "artifacts", label: "Artifacts", icon: Download },
                      { key: "blueprint", label: "Blueprint", icon: FileText },
                      { key: "state", label: "State Machine", icon: Activity },
                    ].map(({ key, label, icon: Icon }) => (
                      <button
                        key={key}
                        onClick={() => setActiveTab(key)}
                        className={`flex items-center gap-1.5 px-3 py-2 text-[0.65rem] font-medium border-b-2 transition-colors ${
                          activeTab === key ? "" : "border-transparent text-gray-500"
                        }`}
                        style={activeTab === key ? {
                          color: "var(--accent-primary)",
                          borderColor: "var(--accent-primary)",
                        } : {}}
                      >
                        <Icon size={12} />
                        {label}
                      </button>
                    ))}
                  </div>
                  <div className="p-4">
                    {/* Timeline Tab */}
                    {activeTab === "timeline" && (
                      <TimelineView entries={timelineEntries} />
                    )}

                    {/* Artifacts Tab */}
                    {activeTab === "artifacts" && (
                      <div className="space-y-2">
                        {artifactList.length === 0 && (
                          <p className="text-xs text-gray-400 text-center py-4">No artifacts</p>
                        )}
                        {artifactList.map((a: Record<string, any>) => (
                          <div key={a.id}
                            className="flex items-center justify-between p-2 rounded-lg text-xs"
                            style={{ background: "var(--bg)" }}
                          >
                            <div className="flex items-center gap-2">
                              <Download size={12} className="text-gray-400" />
                              <span className="font-medium" style={{ color: "var(--text-primary)" }}>{a.name}</span>
                              <span className="text-gray-400">({a.type})</span>
                            </div>
                            <span className="text-gray-400">
                              {a.size_bytes ? `${(a.size_bytes / 1024).toFixed(1)} KB` : "-"}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Blueprint Tab */}
                    {activeTab === "blueprint" && (
                      <div className="grid grid-cols-2 gap-3 text-xs">
                        <div className="space-y-2 p-2 rounded-lg" style={{ background: "var(--bg)" }}>
                          <h4 className="font-semibold" style={{ color: "var(--text-primary)" }}>Build Info</h4>
                          <p><span className="text-gray-400">Build ID:</span> {blueprint?.build || "-"}</p>
                          <p><span className="text-gray-400">Workspace:</span> {blueprint?.workspace || "-"}</p>
                          <p><span className="text-gray-400">Patch:</span> {blueprint?.patch || "-"}</p>
                          <p><span className="text-gray-400">Deployment:</span> {blueprint?.deployment || "-"}</p>
                        </div>
                        <div className="space-y-2 p-2 rounded-lg" style={{ background: "var(--bg)" }}>
                          <h4 className="font-semibold" style={{ color: "var(--text-primary)" }}>Verification</h4>
                          <p>
                            <span className="text-gray-400">Status:</span>{" "}
                            {blueprint?.verification?.verified ? (
                              <span className="text-[#38B88A]">Verified</span>
                            ) : (
                              <span className="text-gray-400">Pending</span>
                            )}
                          </p>
                          <p><span className="text-gray-400">Coverage:</span> {blueprint?.coverage?.lines || "-"}%</p>
                          <p><span className="text-gray-400">Security:</span> {blueprint?.security_report?.passed ? "Passed" : "Pending"}</p>
                        </div>
                        <div className="space-y-2 p-2 rounded-lg col-span-2" style={{ background: "var(--bg)" }}>
                          <h4 className="font-semibold" style={{ color: "var(--text-primary)" }}>Learning & Recommendations</h4>
                          <div className="grid grid-cols-2 gap-2">
                            <div>
                              <p className="text-gray-400 mb-1">Learning References ({blueprint?.learning_references?.length || 0})</p>
                              {(blueprint?.learning_references || []).slice(0, 3).map((r: Record<string, any>, i: number) => (
                                <p key={i} className="truncate text-gray-500">{r.content || r.lesson_id}</p>
                              ))}
                            </div>
                            <div>
                              <p className="text-gray-400 mb-1">Recommendations ({blueprint?.recommendation_references?.length || 0})</p>
                              {(blueprint?.recommendation_references || []).slice(0, 3).map((r: Record<string, any>, i: number) => (
                                <p key={i} className="truncate text-gray-500">{r.title || r.rec_id}</p>
                              ))}
                            </div>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* State Machine Tab */}
                    {activeTab === "state" && (
                      <div className="space-y-3">
                        <div className="flex flex-wrap gap-1.5">
                          {["pending", "queued", "running", "waiting_approval", "paused", "retrying", "completed", "failed", "cancelled", "rolled_back", "resumed"].map((s) => (
                            <span
                              key={s}
                              className={`rounded-full px-2 py-0.5 text-[0.55rem] font-medium capitalize ${
                                s === selected.state
                                  ? "ring-2 ring-offset-1 ring-[#38B88A]"
                                  : ""
                              } ${STATE_COLORS[s] || "bg-gray-100 text-gray-600"}`}
                            >
                              {s.replace(/_/g, " ")}
                            </span>
                          ))}
                        </div>
                        <div className="text-xs text-gray-500">
                          Current state: <strong style={{ color: "var(--text-primary)" }}>{selected.state?.replace(/_/g, " ")}</strong>
                          {selected.error && (
                            <p className="text-red-500 mt-1">Error: {selected.error}</p>
                          )}
                        </div>
                        <div className="overflow-x-auto">
                          <pre className="text-[0.5rem] text-gray-400 font-mono whitespace-pre">
{`State Machine: ${selected.state}
  ├─ Stages Completed: ${(selected.stages_completed || []).join(", ") || "none"}
  ├─ Stages Failed: ${(selected.stages_failed || []).join(", ") || "none"}
  ├─ Current Stage: ${selected.current_stage || "none"}
  ├─ Rollback: ${selected.state === "rolled_back" ? "Yes" : "No"}
  └─ Delivery ID: ${selected.delivery_id}`}
                          </pre>
                        </div>
                      </div>
                    )}
                  </div>
                </motion.div>
              </>
            )}
          </div>
        </div>
      </motion.div>
    </CortexShell>
  )
}
