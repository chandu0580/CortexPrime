"use client"

import { useState, useMemo } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Target, Clock, FileText, Layers, Puzzle, Users, Brain,
  CheckCircle2, AlertCircle, Loader2, ChevronRight, GitBranch,
  Activity, Zap, Archive, Play, Pause, BarChart3, Search,
  Filter, RefreshCw, ListRestart, ArrowRight, CircleDot,
} from "lucide-react"
import CortexShell from "@/components/layout/CortexShell"
import { cn } from "@/utils/cn"
import { stagger, variants } from "@/lib/motion-tokens"

type MissionStatus = "draft" | "running" | "paused" | "completed" | "failed" | "cancelled"
type MissionStage = "intake" | "analysis" | "planning" | "decomposition" | "assignment" | "execution" | "review" | "completion"

interface Mission {
  id: string
  title: string
  description: string
  status: MissionStatus
  priority: "low" | "medium" | "high" | "critical"
  stage: MissionStage
  progress: number
  createdAt: string
  agentCount: number
  tags: string[]
  owner: string
}

interface TimelineEvent {
  id: string
  type: "stage_change" | "agent_action" | "system_event" | "user_intervention"
  message: string
  timestamp: string
  actor: string
  status: "completed" | "running" | "failed" | "pending"
}

interface Artifact {
  id: string
  name: string
  type: "report" | "dataset" | "code" | "document" | "insight" | "decision"
  createdAt: string
  size: string
}

interface ReasoningStep {
  id: string
  step: string
  description: string
  status: "pending" | "in_progress" | "completed" | "failed"
  confidence: number
}

const mockMissions: Mission[] = [
  { id: "M-001", title: "Q2 Market Intelligence", description: "Comprehensive market analysis for Q2 2026 planning", status: "running", priority: "high", stage: "execution", progress: 65, createdAt: "2026-07-15T08:00:00Z", agentCount: 4, tags: ["market", "Q2"], owner: "Alex Morgan" },
  { id: "M-002", title: "Competitor Landscape", description: "Map competitor positioning and product strategy", status: "running", priority: "critical", stage: "execution", progress: 42, createdAt: "2026-07-14T10:30:00Z", agentCount: 3, tags: ["competitor"], owner: "Sarah Chen" },
  { id: "M-003", title: "Customer Sentiment Analysis", description: "Analyze customer feedback from support channels", status: "completed", priority: "medium", stage: "completion", progress: 100, createdAt: "2026-07-13T09:00:00Z", agentCount: 2, tags: ["customer"], owner: "Alex Morgan" },
  { id: "M-004", title: "Infrastructure Audit", description: "Full security and compliance audit of cloud infrastructure", status: "draft", priority: "high", stage: "intake", progress: 0, createdAt: "2026-07-16T14:00:00Z", agentCount: 0, tags: ["security"], owner: "Unassigned" },
  { id: "M-005", title: "Pricing Optimization", description: "Data-driven pricing model for enterprise tier", status: "paused", priority: "medium", stage: "analysis", progress: 28, createdAt: "2026-07-12T11:00:00Z", agentCount: 2, tags: ["pricing"], owner: "Sarah Chen" },
  { id: "M-006", title: "Product Launch Plan", description: "Go-to-market strategy for new product release", status: "failed", priority: "high", stage: "review", progress: 85, createdAt: "2026-07-10T07:00:00Z", agentCount: 5, tags: ["launch"], owner: "Alex Morgan" },
]

const mockTimeline: TimelineEvent[] = [
  { id: "t1", type: "stage_change", message: "Mission progressed to Execution stage", timestamp: "2026-07-15T10:30:00Z", actor: "System", status: "completed" },
  { id: "t2", type: "agent_action", message: "Research Agent completed competitive analysis", timestamp: "2026-07-15T10:28:00Z", actor: "Research Agent", status: "completed" },
  { id: "t3", type: "agent_action", message: "Data Analyst extracting market indices", timestamp: "2026-07-15T10:25:00Z", actor: "Data Analyst", status: "running" },
  { id: "t4", type: "system_event", message: "Governance policy check passed", timestamp: "2026-07-15T10:20:00Z", actor: "System", status: "completed" },
  { id: "t5", type: "user_intervention", message: "Alex adjusted priority from medium to high", timestamp: "2026-07-15T10:15:00Z", actor: "Alex Morgan", status: "completed" },
  { id: "t6", type: "stage_change", message: "Mission entered Planning stage", timestamp: "2026-07-15T09:45:00Z", actor: "System", status: "completed" },
]

const mockArtifacts: Artifact[] = [
  { id: "a1", name: "Market Analysis Report", type: "report", createdAt: "2026-07-15", size: "2.4 MB" },
  { id: "a2", name: "Competitor Dataset", type: "dataset", createdAt: "2026-07-15", size: "8.1 MB" },
  { id: "a3", name: "Strategy Document", type: "document", createdAt: "2026-07-14", size: "1.2 MB" },
  { id: "a4", name: "Key Insights Summary", type: "insight", createdAt: "2026-07-14", size: "0.3 MB" },
]

const mockReasoning: ReasoningStep[] = [
  { id: "r1", step: "Goal Analysis", description: "Parse and validate mission objective", status: "completed", confidence: 0.95 },
  { id: "r2", step: "Context Gathering", description: "Retrieve relevant context from memory", status: "completed", confidence: 0.88 },
  { id: "r3", step: "Constraint Identification", description: "Identify resource and policy constraints", status: "completed", confidence: 0.82 },
  { id: "r4", step: "Strategy Formulation", description: "Develop execution strategy with agent allocation", status: "completed", confidence: 0.79 },
  { id: "r5", step: "Risk Assessment", description: "Evaluate potential failure modes and mitigations", status: "in_progress", confidence: 0.0 },
  { id: "r6", step: "Execution Plan", description: "Generate detailed step-by-step execution plan", status: "pending", confidence: 0.0 },
]

const stageLabels: Record<MissionStage, string> = {
  intake: "Intake", analysis: "Analysis", planning: "Planning", decomposition: "Decomposition",
  assignment: "Assignment", execution: "Execution", review: "Review", completion: "Completion",
}

const statusConfig: Record<MissionStatus, { color: string; bg: string; dot: string }> = {
  running: { color: "var(--success)", bg: "var(--success-muted)", dot: "var(--success)" },
  completed: { color: "var(--text-secondary)", bg: "var(--surface-raised)", dot: "var(--text-secondary)" },
  failed: { color: "var(--danger)", bg: "var(--danger-muted)", dot: "var(--danger)" },
  draft: { color: "var(--text-muted)", bg: "var(--surface-raised)", dot: "var(--text-muted)" },
  paused: { color: "var(--warning)", bg: "var(--warning-muted)", dot: "var(--warning)" },
  cancelled: { color: "var(--text-secondary)", bg: "var(--surface-raised)", dot: "var(--text-secondary)" },
}

const stageOrder: MissionStage[] = ["intake", "analysis", "planning", "decomposition", "assignment", "execution", "review", "completion"]

export default function MissionCenterPage() {
  const [search, setSearch] = useState("")
  const [statusFilter, setStatusFilter] = useState<MissionStatus | "all">("all")
  const [selectedMission, setSelectedMission] = useState<Mission | null>(null)
  const [activeDetailTab, setActiveDetailTab] = useState<"timeline" | "artifacts" | "reasoning" | "connectors">("timeline")

  const filtered = useMemo(() => {
    return mockMissions.filter((m) => {
      if (statusFilter !== "all" && m.status !== statusFilter) return false
      if (search && !m.title.toLowerCase().includes(search.toLowerCase()) && !m.id.toLowerCase().includes(search.toLowerCase())) return false
      return true
    })
  }, [search, statusFilter])

  const detailTabs = [
    { id: "timeline" as const, label: "Timeline", icon: Clock },
    { id: "artifacts" as const, label: "Artifacts", icon: FileText },
    { id: "reasoning" as const, label: "Reasoning Trace", icon: Brain },
    { id: "connectors" as const, label: "Connectors", icon: Puzzle },
  ]

  return (
    <CortexShell title="Mission Center" subtitle="Mission lifecycle, timeline, artifacts & agent collaboration">
      <div className="mx-auto max-w-[1600px] space-y-6 p-6">
        <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-[10px]" style={{ background: "var(--success-muted)" }}>
              <Target size={18} style={{ color: "var(--success)" }} />
            </div>
            <div>
              <h1 className="text-[1.3rem] font-extrabold tracking-tight" style={{ color: "var(--text-primary)" }}>Mission Center</h1>
              <p className="text-[0.75rem]" style={{ color: "var(--text-secondary)" }}>Manage mission lifecycle, track progress, review artifacts</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button className="flex items-center gap-1.5 rounded-[10px] px-3 py-1.5 text-[0.75rem] font-semibold hover:bg-[var(--surface-raised)]" style={{ border: "1px solid var(--border)", background: "var(--surface)", color: "var(--text-secondary)" }}>
              <Filter className="h-3.5 w-3.5" /> Filter
            </button>
            <button className="flex items-center gap-1.5 rounded-[10px] px-3 py-1.5 text-[0.75rem] font-semibold text-white shadow-sm hover:bg-[#2F9F77]" style={{ background: "var(--success)" }}>
              <Play className="h-3.5 w-3.5" /> New Mission
            </button>
          </div>
        </motion.div>

        <div className="flex items-center gap-4">
          <div className="relative flex-1 max-w-xs">
            <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2" style={{ color: "var(--text-muted)" }} />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search missions..."
              aria-label="Search missions"
              className="h-9 w-full rounded-[10px] pl-9 pr-3 text-[0.8rem] outline-none placeholder:text-[var(--text-muted)] focus:border-[var(--accent-muted)]"
              style={{ border: "1px solid var(--border)", background: "var(--surface)", color: "var(--text-primary)" }}
            />
          </div>
          <div className="flex gap-1 rounded-[10px] p-1" style={{ background: "var(--surface-raised)" }}>
            {(["all", "running", "completed", "failed", "draft", "paused"] as const).map((s) => (
              <button
                key={s}
                onClick={() => setStatusFilter(s)}
                aria-pressed={statusFilter === s}
                className={cn(
                  "rounded-[8px] px-3 py-1.5 text-[0.7rem] font-semibold transition-all capitalize",
                  statusFilter === s ? "shadow-sm" : "hover:text-[var(--text-primary)]"
                )}
                style={{
                  background: statusFilter === s ? "var(--surface)" : "transparent",
                  color: statusFilter === s ? "var(--text-primary)" : "var(--text-secondary)",
                }}
              >{s}</button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1fr_420px]">
          <div className="space-y-3">
            <AnimatePresence>
              {filtered.length === 0 ? (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col items-center py-12 text-center">
                  <Target className="h-12 w-12 mb-3" style={{ color: "var(--text-muted)" }} />
                  <p className="text-[0.9rem] font-semibold" style={{ color: "var(--text-secondary)" }}>No missions found</p>
                  <p className="text-[0.75rem]" style={{ color: "var(--text-muted)" }}>Create a new mission to get started</p>
                </motion.div>
              ) : (
                filtered.map((mission, i) => {
                  const sc = statusConfig[mission.status]
                  const priorityStyle = mission.priority === "critical"
                    ? { background: "var(--danger-muted)", color: "var(--danger)" }
                    : mission.priority === "high"
                    ? { background: "var(--warning-muted)", color: "var(--warning)" }
                    : mission.priority === "medium"
                    ? { background: "var(--success-muted)", color: "var(--success)" }
                    : { background: "var(--surface-raised)", color: "var(--text-muted)" }
                  return (
                    <motion.div
                      key={mission.id}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: i * 0.03 }}
                      onClick={() => setSelectedMission(mission)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault()
                          setSelectedMission(mission)
                        }
                      }}
                      role="button"
                      tabIndex={0}
                      className={cn(
                        "rounded-[16px] p-5 cursor-pointer transition-all",
                        selectedMission?.id === mission.id ? "shadow-sm" : "hover:shadow-sm"
                      )}
                      style={{
                        border: selectedMission?.id === mission.id ? "1px solid var(--success)" : "1px solid var(--border)",
                        background: selectedMission?.id === mission.id ? "var(--success-muted)" : "var(--surface)",
                      }}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2.5">
                            <h3 className="text-[0.9rem] font-bold truncate" style={{ color: "var(--text-primary)" }}>{mission.title}</h3>
                            <span
                              className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[0.6rem] font-semibold"
                              style={{ background: sc.bg, color: sc.color }}
                            >
                              <span className="h-1.5 w-1.5 rounded-full" style={{ background: sc.dot }} />
                              {mission.status}
                            </span>
                          </div>
                          <p className="mt-1 text-[0.75rem] line-clamp-1" style={{ color: "var(--text-secondary)" }}>{mission.description}</p>
                        </div>
                        <div className="flex items-center gap-1.5 shrink-0">
                          <span
                            className="rounded-[6px] px-2 py-0.5 text-[0.6rem] font-bold uppercase"
                            style={priorityStyle}
                          >{mission.priority}</span>
                          <span className="text-[0.7rem] font-medium" style={{ color: "var(--text-muted)" }}>{mission.agentCount} agents</span>
                        </div>
                      </div>

                      <div className="mt-3 flex items-center gap-4">
                        <div className="flex-1">
                          <div className="flex items-center justify-between text-[0.65rem] mb-1" style={{ color: "var(--text-muted)" }}>
                            <span>Progress</span>
                            <span className="font-semibold">{mission.progress}%</span>
                          </div>
                          <div className="h-1.5 w-full rounded-full overflow-hidden" style={{ background: "var(--border)" }}>
                            <div
                              className="h-full rounded-full transition-all"
                              style={{ width: `${mission.progress}%`, background: "var(--success)" }}
                            />
                          </div>
                        </div>
                        <div className="flex items-center gap-3 text-[0.65rem]" style={{ color: "var(--text-muted)" }}>
                          <span className="flex items-center gap-1"><Layers className="h-3 w-3" /> {stageLabels[mission.stage]}</span>
                          <span className="flex items-center gap-1"><Users className="h-3 w-3" /> {mission.owner}</span>
                        </div>
                      </div>
                    </motion.div>
                  )
                })
              )}
            </AnimatePresence>
          </div>

          <AnimatePresence mode="wait">
            {selectedMission ? (
              <motion.div key={selectedMission.id} initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 20 }} className="space-y-4">
                <div className="rounded-[16px] p-5" style={{ border: "1px solid var(--border)", background: "var(--surface)" }}>
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <h2 className="text-[1rem] font-bold" style={{ color: "var(--text-primary)" }}>{selectedMission.title}</h2>
                      <p className="text-[0.72rem] mt-0.5" style={{ color: "var(--text-secondary)" }}>{selectedMission.id}</p>
                    </div>
                    <div className="flex gap-1">
                      <button aria-label="Pause mission" className="flex h-7 w-7 items-center justify-center rounded-[8px] hover:bg-[var(--surface-raised)]" style={{ color: "var(--text-muted)" }}>
                        <Pause className="h-3.5 w-3.5" />
                      </button>
                      <button aria-label="Reset mission" className="flex h-7 w-7 items-center justify-center rounded-[8px] hover:bg-[var(--surface-raised)]" style={{ color: "var(--text-muted)" }}>
                        <ListRestart className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>

                  <div className="flex flex-wrap gap-2 mb-4">
                    {selectedMission.tags.map((t) => (
                      <span key={t} className="rounded-full px-2 py-0.5 text-[0.6rem] font-semibold" style={{ background: "var(--surface-raised)", color: "var(--text-secondary)" }}>{t}</span>
                    ))}
                  </div>

                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-[0.65rem]" style={{ color: "var(--text-muted)" }}>
                      <span>Lifecycle Progress</span>
                      <span className="font-semibold">{selectedMission.progress}%</span>
                    </div>
                    <div className="flex items-center gap-1">
                      {stageOrder.map((stage) => {
                        const currentIdx = stageOrder.indexOf(selectedMission.stage)
                        const stageIdx = stageOrder.indexOf(stage)
                        const isComplete = stageIdx < currentIdx
                        const isCurrent = stageIdx === currentIdx
                        return (
                          <div key={stage} className="flex-1 flex flex-col items-center">
                            <div
                              className="h-2 w-full rounded-full transition-colors"
                              style={{
                                background: isComplete || isCurrent ? "var(--success)" : "var(--border)",
                              }}
                            />
                            <span
                              className="text-[0.5rem] mt-1 text-center leading-tight"
                              style={{
                                color: isCurrent ? "var(--success)" : "var(--text-muted)",
                                fontWeight: isCurrent ? 600 : 400,
                              }}
                            >{stageLabels[stage]}</span>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                </div>

                <div className="flex gap-1 rounded-[10px] p-1" role="tablist" aria-label="Mission detail tabs" style={{ background: "var(--surface-raised)" }}>
                  {detailTabs.map((tab) => {
                    const Icon = tab.icon
                    const active = activeDetailTab === tab.id
                    return (
                      <button
                        key={tab.id}
                        role="tab"
                        aria-selected={active}
                        aria-controls={`detail-tabpanel-${tab.id}`}
                        id={`detail-tab-${tab.id}`}
                        onClick={() => setActiveDetailTab(tab.id)}
                        className={cn(
                          "flex items-center gap-1.5 rounded-[8px] px-3 py-1.5 text-[0.7rem] font-semibold transition-all",
                          active ? "shadow-sm" : "hover:text-[var(--text-primary)]"
                        )}
                        style={{
                          background: active ? "var(--surface)" : "transparent",
                          color: active ? "var(--text-primary)" : "var(--text-secondary)",
                        }}
                      >
                        <Icon className="h-3 w-3" /> {tab.label}
                      </button>
                    )
                  })}
                </div>

                {activeDetailTab === "timeline" && (
                  <div role="tabpanel" id="detail-tabpanel-timeline" aria-labelledby="detail-tab-timeline">
                    <TimelineView events={mockTimeline} />
                  </div>
                )}
                {activeDetailTab === "artifacts" && (
                  <div role="tabpanel" id="detail-tabpanel-artifacts" aria-labelledby="detail-tab-artifacts">
                    <ArtifactsView artifacts={mockArtifacts} />
                  </div>
                )}
                {activeDetailTab === "reasoning" && (
                  <div role="tabpanel" id="detail-tabpanel-reasoning" aria-labelledby="detail-tab-reasoning">
                    <ReasoningTraceView steps={mockReasoning} />
                  </div>
                )}
                {activeDetailTab === "connectors" && (
                  <div role="tabpanel" id="detail-tabpanel-connectors" aria-labelledby="detail-tab-connectors">
                    <ConnectorActivityView />
                  </div>
                )}
              </motion.div>
            ) : (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex flex-col items-center justify-center py-16 text-center rounded-[16px] border border-dashed"
                style={{ borderColor: "var(--border)", background: "var(--surface)" }}
              >
                <Target className="h-12 w-12 mb-4" style={{ color: "var(--text-muted)" }} />
                <p className="text-[0.9rem] font-semibold" style={{ color: "var(--text-secondary)" }}>Select a mission</p>
                <p className="text-[0.75rem] mt-1" style={{ color: "var(--text-muted)" }}>Click on a mission to view details</p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </CortexShell>
  )
}

function TimelineView({ events }: { events: TimelineEvent[] }) {
  return (
    <div className="rounded-[16px] p-5" style={{ border: "1px solid var(--border)", background: "var(--surface)" }}>
      <h3 className="text-[0.85rem] font-bold mb-4 flex items-center gap-2" style={{ color: "var(--text-primary)" }}>
        <Clock className="h-4 w-4" style={{ color: "var(--success)" }} /> Session Timeline
      </h3>
      <div className="relative space-y-0">
        {events.map((event, i) => {
          const statusIcon = event.status === "completed" ? CheckCircle2 : event.status === "running" ? Loader2 : event.status === "failed" ? AlertCircle : CircleDot
          const statusColor = event.status === "completed" ? "var(--success)" : event.status === "running" ? "var(--success)" : event.status === "failed" ? "var(--danger)" : "var(--text-muted)"
          const Icon = statusIcon
          const isRunning = event.status === "running"
          return (
            <div key={event.id} className="relative flex gap-4 pb-5 last:pb-0">
              {i < events.length - 1 && <div className="absolute left-[11px] top-6 bottom-0 w-px" style={{ background: "var(--border)" }} />}
              <div
                className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full"
                style={{ background: isRunning ? "var(--success-muted)" : "var(--surface-raised)" }}
              >
                {isRunning ? (
                  <Loader2 className="h-3 w-3 animate-spin" style={{ color: statusColor }} />
                ) : (
                  <Icon className="h-3 w-3" style={{ color: statusColor }} />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[0.78rem] font-semibold" style={{ color: "var(--text-primary)" }}>{event.message}</p>
                <div className="flex items-center gap-2 mt-0.5 text-[0.62rem]" style={{ color: "var(--text-muted)" }}>
                  <span>{event.actor}</span>
                  <span className="h-3 w-px" style={{ background: "var(--border)" }} />
                  <span>{new Date(event.timestamp).toLocaleTimeString()}</span>
                  <span className="capitalize font-semibold" style={{ color: statusColor }}>{event.status}</span>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function ArtifactsView({ artifacts }: { artifacts: Artifact[] }) {
  const typeIcons: Record<string, typeof FileText> = { report: FileText, dataset: Layers, code: GitBranch, document: FileText, insight: Brain, decision: CheckCircle2 }
  const typeColors: Record<string, string> = { report: "var(--success)", dataset: "#3B82F6", code: "#8B5CF6", document: "var(--warning)", insight: "#EC4899", decision: "var(--text-secondary)" }
  const typeBg: Record<string, string> = { report: "var(--success-muted)", dataset: "#EFF6FF", code: "#F5F3FF", document: "var(--warning-muted)", insight: "#FDF2F8", decision: "var(--surface-raised)" }

  return (
    <div className="rounded-[16px] p-5" style={{ border: "1px solid var(--border)", background: "var(--surface)" }}>
      <h3 className="text-[0.85rem] font-bold mb-4 flex items-center gap-2" style={{ color: "var(--text-primary)" }}>
        <Archive className="h-4 w-4" style={{ color: "var(--success)" }} /> Artifacts ({artifacts.length})
      </h3>
      <div className="space-y-2">
        {artifacts.map((a) => {
          const Icon = typeIcons[a.type] ?? FileText
          return (
            <div key={a.id} className="flex items-center gap-3 rounded-[10px] p-3 transition-colors cursor-pointer hover:bg-[var(--surface-raised)]" style={{ border: "1px solid var(--border)" }}>
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[8px]" style={{ background: typeBg[a.type] }}>
                <Icon className="h-4 w-4" style={{ color: typeColors[a.type] }} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[0.78rem] font-semibold truncate" style={{ color: "var(--text-primary)" }}>{a.name}</p>
                <div className="flex items-center gap-2 text-[0.6rem]" style={{ color: "var(--text-muted)" }}>
                  <span className="capitalize">{a.type}</span>
                  <span className="h-3 w-px" style={{ background: "var(--border)" }} />
                  <span>{a.createdAt}</span>
                </div>
              </div>
              <span className="text-[0.65rem] font-medium" style={{ color: "var(--text-muted)" }}>{a.size}</span>
              <ChevronRight className="h-3.5 w-3.5" style={{ color: "var(--text-muted)" }} />
            </div>
          )
        })}
      </div>
    </div>
  )
}

function ReasoningTraceView({ steps }: { steps: ReasoningStep[] }) {
  return (
    <div className="rounded-[16px] p-5" style={{ border: "1px solid var(--border)", background: "var(--surface)" }}>
      <h3 className="text-[0.85rem] font-bold mb-4 flex items-center gap-2" style={{ color: "var(--text-primary)" }}>
        <Brain className="h-4 w-4" style={{ color: "var(--success)" }} /> Reasoning Trace
      </h3>
      <div className="space-y-0">
        {steps.map((step) => (
          <div key={step.id} className="relative flex gap-4 pb-5 last:pb-0">
            {steps.indexOf(step) < steps.length - 1 && <div className="absolute left-[11px] top-6 bottom-0 w-px" style={{ background: "var(--border)" }} />}
            <div
              className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full"
              style={{
                background: step.status === "completed" || step.status === "in_progress"
                  ? "var(--success-muted)"
                  : step.status === "failed"
                    ? "var(--danger-muted)"
                    : "var(--surface-raised)",
              }}
            >
              {step.status === "completed" && <CheckCircle2 className="h-3 w-3" style={{ color: "var(--success)" }} />}
              {step.status === "in_progress" && <Loader2 className="h-3 w-3 animate-spin" style={{ color: "var(--success)" }} />}
              {step.status === "failed" && <AlertCircle className="h-3 w-3" style={{ color: "var(--danger)" }} />}
              {step.status === "pending" && <CircleDot className="h-3 w-3" style={{ color: "var(--text-muted)" }} />}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between">
                <p className="text-[0.78rem] font-semibold" style={{ color: "var(--text-primary)" }}>{step.step}</p>
                {step.confidence > 0 && (
                  <span className="text-[0.65rem] font-bold" style={{ color: "var(--success)" }}>{(step.confidence * 100).toFixed(0)}%</span>
                )}
              </div>
              <p className="text-[0.68rem]" style={{ color: "var(--text-secondary)" }}>{step.description}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function ConnectorActivityView() {
  const connectors = [
    { name: "Browser", status: "active", actions: 142, icon: Activity },
    { name: "Memory", status: "active", actions: 89, icon: Database },
    { name: "Research", status: "active", actions: 56, icon: Search },
    { name: "Voice", status: "idle", actions: 12, icon: Mic },
    { name: "Code", status: "active", actions: 34, icon: GitBranch },
  ]
  return (
    <div className="rounded-[16px] p-5" style={{ border: "1px solid var(--border)", background: "var(--surface)" }}>
      <h3 className="text-[0.85rem] font-bold mb-4 flex items-center gap-2" style={{ color: "var(--text-primary)" }}>
        <Puzzle className="h-4 w-4" style={{ color: "var(--success)" }} /> Connector Activity
      </h3>
      <div className="space-y-2">
        {connectors.map((c) => {
          const Icon = c.icon
          const isActive = c.status === "active"
          return (
            <div key={c.name} className="flex items-center gap-3 rounded-[10px] p-3" style={{ border: "1px solid var(--border)" }}>
              <div
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[8px]"
                style={{ background: isActive ? "var(--success-muted)" : "var(--surface-raised)" }}
              >
                <Icon className="h-4 w-4" style={{ color: isActive ? "var(--success)" : "var(--text-muted)" }} />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <p className="text-[0.78rem] font-semibold" style={{ color: "var(--text-primary)" }}>{c.name}</p>
                  <span
                    className="inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[0.55rem] font-semibold"
                    style={{
                      background: isActive ? "var(--success-muted)" : "var(--surface-raised)",
                      color: isActive ? "var(--success)" : "var(--text-muted)",
                    }}
                  >
                    <span className="h-1 w-1 rounded-full" style={{ background: isActive ? "var(--success)" : "var(--text-muted)" }} />
                    {c.status}
                  </span>
                </div>
              </div>
              <span className="text-[0.75rem] font-bold" style={{ color: "var(--text-secondary)" }}>{c.actions}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

const Mic = ({ className }: { className?: string }) => <Activity className={className} />
const Database = ({ className }: { className?: string }) => <Layers className={className} />
