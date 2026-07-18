"use client"

import { useState, useMemo } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Bot, Users, Brain, Cpu, Activity, CheckCircle2, AlertCircle,
  Loader2, Search, Filter, BarChart3, GitBranch, Share2,
  Server, Clock, Zap, TrendingUp, Layers, CircleDot,
  ChevronRight, RefreshCw, Play, Pause,
} from "lucide-react"
import CortexShell from "@/components/layout/CortexShell"
import { cn } from "@/utils/cn"
import { stagger, variants } from "@/lib/motion-tokens"

interface Agent {
  id: string
  name: string
  type: string
  status: "idle" | "assigned" | "running" | "completed" | "failed"
  model: string
  capabilities: string[]
  currentTask?: string
  missionId?: string
  memoryUsage: number
  uptime: string
  tasksCompleted: number
  successRate: number
  lastActive: string
}

interface SharedMemoryEntry {
  id: string
  key: string
  value: string
  source: string
  updatedAt: string
  accessCount: number
}

interface DelegationEdge {
  from: string
  to: string
  task: string
  status: "active" | "completed" | "failed"
}

const mockAgents: Agent[] = [
  { id: "a1", name: "Orchestrator", type: "Supervisor", status: "running", model: "GPT-4o", capabilities: ["Planning", "Delegation", "Monitoring"], currentTask: "Q2 Market Intelligence", missionId: "M-001", memoryUsage: 68, uptime: "72h", tasksCompleted: 142, successRate: 97.2, lastActive: "now" },
  { id: "a2", name: "Research Agent", type: "Research", status: "running", model: "GPT-4o", capabilities: ["Web Search", "Data Extraction", "Analysis"], currentTask: "Competitor Analysis", missionId: "M-001", memoryUsage: 54, uptime: "48h", tasksCompleted: 89, successRate: 94.8, lastActive: "now" },
  { id: "a3", name: "Data Analyst", type: "Analysis", status: "running", model: "Claude 3.5", capabilities: ["Data Processing", "Visualization", "Reporting"], currentTask: "Market Indices", missionId: "M-001", memoryUsage: 72, uptime: "36h", tasksCompleted: 56, successRate: 96.1, lastActive: "2m ago" },
  { id: "a4", name: "Memory Agent", type: "Memory", status: "idle", model: "GPT-4o-mini", capabilities: ["Retrieval", "Storage", "Indexing"], memoryUsage: 81, uptime: "96h", tasksCompleted: 234, successRate: 99.1, lastActive: "15m ago" },
  { id: "a5", name: "Critic Agent", type: "Evaluation", status: "completed", model: "Claude 3.5", capabilities: ["Review", "Validation", "Quality Check"], currentTask: "Report Review", missionId: "M-003", memoryUsage: 45, uptime: "24h", tasksCompleted: 67, successRate: 92.5, lastActive: "1h ago" },
  { id: "a6", name: "Voice Agent", type: "Voice", status: "idle", model: "GPT-4o", capabilities: ["Speech", "Synthesis", "Transcription"], memoryUsage: 32, uptime: "12h", tasksCompleted: 23, successRate: 98.3, lastActive: "3h ago" },
]

const mockMemoryEntries: SharedMemoryEntry[] = [
  { id: "m1", key: "market_trends_q2", value: "S&P 500 up 1.02%, NASDAQ up 1.25%", source: "Research Agent", updatedAt: "2026-07-15T10:30:00Z", accessCount: 12 },
  { id: "m2", key: "competitor_insights", value: "Competitor A launched new product line", source: "Data Analyst", updatedAt: "2026-07-15T10:28:00Z", accessCount: 8 },
  { id: "m3", key: "policy_constraints", value: "Data retention: 90 days, PII masking required", source: "Memory Agent", updatedAt: "2026-07-15T09:00:00Z", accessCount: 45 },
  { id: "m4", key: "governance_checks", value: "All policies passed, no violations", source: "Critic Agent", updatedAt: "2026-07-15T09:30:00Z", accessCount: 23 },
]

const delegationEdges: DelegationEdge[] = [
  { from: "a1", to: "a2", task: "Competitive Analysis", status: "active" },
  { from: "a1", to: "a3", task: "Data Extraction", status: "active" },
  { from: "a2", to: "a4", task: "Store Findings", status: "completed" },
  { from: "a3", to: "a4", task: "Cache Dataset", status: "completed" },
  { from: "a1", to: "a5", task: "Review Results", status: "completed" },
]

const statusConfig: Record<string, { color: string; bg: string; dot: string }> = {
  running: { color: "var(--accent)", bg: "var(--accent-muted)", dot: "var(--accent)" },
  idle: { color: "var(--text-muted)", bg: "var(--surface-raised)", dot: "var(--text-muted)" },
  assigned: { color: "var(--accent)", bg: "var(--accent-muted)", dot: "var(--accent)" },
  completed: { color: "var(--text-secondary)", bg: "var(--surface-raised)", dot: "var(--text-secondary)" },
  failed: { color: "var(--danger)", bg: "var(--danger-muted)", dot: "var(--danger)" },
}

export default function AgentCenterPage() {
  const [search, setSearch] = useState("")
  const [statusFilter, setStatusFilter] = useState<string>("all")
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null)
  const [activeTab, setActiveTab] = useState<"agents" | "delegation" | "memory" | "performance">("agents")

  const filtered = useMemo(() => {
    return mockAgents.filter((a) => {
      if (statusFilter !== "all" && a.status !== statusFilter) return false
      if (search && !a.name.toLowerCase().includes(search.toLowerCase())) return false
      return true
    })
  }, [search, statusFilter])

  const kpis = [
    { label: "Total Agents", value: mockAgents.length.toString(), icon: Bot, color: "var(--accent)" },
    { label: "Active", value: mockAgents.filter((a) => a.status === "running").length.toString(), icon: Activity, color: "var(--accent)" },
    { label: "Idle", value: mockAgents.filter((a) => a.status === "idle").length.toString(), icon: Cpu, color: "var(--warning)" },
    { label: "Success Rate", value: `${(mockAgents.reduce((s, a) => s + a.successRate, 0) / mockAgents.length).toFixed(1)}%`, icon: TrendingUp, color: "var(--accent)" },
    { label: "Tasks Today", value: mockAgents.reduce((s, a) => s + a.tasksCompleted, 0).toLocaleString(), icon: BarChart3, color: "var(--accent)" },
  ]

  const tabs = [
    { id: "agents" as const, label: "Registered Agents", icon: Bot },
    { id: "delegation" as const, label: "Delegation Graph", icon: GitBranch },
    { id: "memory" as const, label: "Shared Memory", icon: Layers },
    { id: "performance" as const, label: "Performance", icon: BarChart3 },
  ]

  return (
    <CortexShell title="Agent Center" subtitle="Registered agents, delegation graph, shared memory & performance">
      <div className="mx-auto max-w-[1600px] space-y-6 p-6">
        <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-[10px]" style={{ background: "var(--accent-muted)" }}>
              <Bot size={18} style={{ color: "var(--accent)" }} />
            </div>
            <div>
              <h1 className="text-[1.3rem] font-extrabold tracking-tight" style={{ color: "var(--text-primary)" }}>Agent Center</h1>
              <p className="text-[0.75rem]" style={{ color: "var(--text-secondary)" }}>Monitor, manage, and analyze agent operations</p>
            </div>
          </div>
        </motion.div>

        <motion.div variants={stagger(0.04)} initial="hidden" animate="visible" className="grid gap-4 sm:grid-cols-3 lg:grid-cols-5">
          {kpis.map((k) => {
            const Icon = k.icon
            return (
              <div key={k.label} className="rounded-[14px] p-4" style={{ border: "1px solid var(--border)", background: "var(--surface)" }}>
                <div className="flex items-center justify-between">
                  <span className="text-[0.65rem] font-semibold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>{k.label}</span>
                  <Icon className="h-4 w-4" style={{ color: k.color }} />
                </div>
                <p className="mt-1.5 text-[1.3rem] font-extrabold tracking-tight" style={{ color: "var(--text-primary)" }}>{k.value}</p>
              </div>
            )
          })}
        </motion.div>

        <div className="flex items-center gap-1 rounded-[12px] p-1 w-fit" role="tablist" style={{ background: "var(--surface-raised)" }}>
          {tabs.map((tab) => {
            const Icon = tab.icon
            const active = activeTab === tab.id
            return (
              <button
                key={tab.id}
                role="tab"
                aria-selected={active}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "flex items-center gap-2 rounded-[10px] px-4 py-2 text-[0.8rem] font-semibold transition-all",
                  active ? "bg-[var(--surface)] text-[var(--accent)] shadow-sm" : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                )}
              >
                <Icon className="h-4 w-4" /> {tab.label}
              </button>
            )
          })}
        </div>

        {activeTab === "agents" && (
          <div role="tabpanel">
            <div className="flex items-center gap-4 mb-4">
              <div className="relative flex-1 max-w-xs">
                <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2" style={{ color: "var(--text-muted)" }} />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search agents..."
                  aria-label="Search agents"
                  className="h-9 w-full rounded-[10px] pl-9 pr-3 text-[0.8rem] outline-none placeholder:text-[var(--text-muted)] focus:border-[var(--accent-muted)]"
                  style={{ border: "1px solid var(--border)", background: "var(--surface)", color: "var(--text-primary)" }}
                />
              </div>
              <div className="flex gap-1 rounded-[10px] p-1" style={{ background: "var(--surface-raised)" }}>
                {(["all", "running", "idle", "completed", "failed"] as const).map((s) => (
                  <button
                    key={s}
                    aria-pressed={statusFilter === s}
                    onClick={() => setStatusFilter(s)}
                    className={cn(
                      "rounded-[8px] px-3 py-1.5 text-[0.7rem] font-semibold transition-all capitalize",
                      statusFilter === s ? "bg-[var(--surface)] text-[var(--text-primary)] shadow-sm" : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                    )}
                  >{s === "all" ? "All" : s}</button>
                ))}
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <AnimatePresence>
                {filtered.map((agent, i) => {
                  const sc = statusConfig[agent.status]
                  return (
                    <motion.div
                      key={agent.id}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: i * 0.03 }}
                      onClick={() => setSelectedAgent(agent)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault()
                          setSelectedAgent(agent)
                        }
                      }}
                      role="button"
                      tabIndex={0}
                      className={cn(
                        "rounded-[16px] p-5 cursor-pointer transition-all",
                        selectedAgent?.id === agent.id ? "border-[var(--accent)] bg-[var(--accent-muted)] shadow-sm" : "border-[var(--border)] bg-[var(--surface)] hover:shadow-sm"
                      )}
                      style={{ borderWidth: 1, borderStyle: "solid" }}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex items-center gap-3">
                          <div className="flex h-10 w-10 items-center justify-center rounded-[12px]" style={{ background: sc.bg }}>
                            <Bot className="h-5 w-5" style={{ color: sc.color }} />
                          </div>
                          <div>
                            <p className="text-[0.85rem] font-bold" style={{ color: "var(--text-primary)" }}>{agent.name}</p>
                            <p className="text-[0.65rem]" style={{ color: "var(--text-muted)" }}>{agent.type} &middot; {agent.model}</p>
                          </div>
                        </div>
                        <span
                          className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[0.6rem] font-semibold"
                          style={{ color: sc.color, background: sc.bg }}
                        >
                          <span className="h-1.5 w-1.5 rounded-full" style={{ background: sc.dot }} />
                          {agent.status}
                        </span>
                      </div>

                      {agent.currentTask && (
                        <div className="mt-3 rounded-[8px] p-2.5" style={{ background: "var(--surface-raised)", border: "1px solid var(--border)" }}>
                          <p className="text-[0.6rem] font-semibold uppercase" style={{ color: "var(--text-muted)" }}>Current Task</p>
                          <p className="text-[0.75rem] font-medium mt-0.5" style={{ color: "var(--text-primary)" }}>{agent.currentTask}</p>
                        </div>
                      )}

                      <div className="mt-3 flex items-center gap-3 text-[0.65rem]" style={{ color: "var(--text-muted)" }}>
                        <span className="flex items-center gap-1"><Cpu className="h-3 w-3" /> Mem: {agent.memoryUsage}%</span>
                        <span className="flex items-center gap-1"><Zap className="h-3 w-3" /> {agent.tasksCompleted} tasks</span>
                        <span className="flex items-center gap-1"><TrendingUp className="h-3 w-3" /> {agent.successRate}%</span>
                      </div>
                    </motion.div>
                  )
                })}
              </AnimatePresence>
              {filtered.length === 0 && (
                <div className="col-span-full flex flex-col items-center justify-center py-16" style={{ color: "var(--text-muted)" }}>
                  <Search className="h-10 w-10 mb-3" style={{ color: "var(--text-muted)" }} />
                  <p className="text-[0.9rem] font-semibold" style={{ color: "var(--text-secondary)" }}>No agents matching your search</p>
                  <p className="text-[0.75rem] mt-1">Try adjusting your search or filter criteria</p>
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === "delegation" && (
          <div role="tabpanel">
            <DelegationGraphView edges={delegationEdges} agents={mockAgents} />
          </div>
        )}
        {activeTab === "memory" && (
          <div role="tabpanel">
            <SharedMemoryView entries={mockMemoryEntries} />
          </div>
        )}
        {activeTab === "performance" && (
          <div role="tabpanel">
            <PerformanceView agents={mockAgents} />
          </div>
        )}
      </div>
    </CortexShell>
  )
}

function DelegationGraphView({ edges, agents }: { edges: DelegationEdge[]; agents: Agent[] }) {
  return (
    <div className="rounded-[16px] p-6" style={{ border: "1px solid var(--border)", background: "var(--surface)" }}>
      <h3 className="text-[0.85rem] font-bold mb-4 flex items-center gap-2" style={{ color: "var(--text-primary)" }}>
        <GitBranch className="h-4 w-4" style={{ color: "var(--accent)" }} /> Delegation Graph
      </h3>
      <div className="flex flex-col items-center py-8">
        <div className="flex flex-wrap justify-center gap-8">
          {agents.slice(0, 4).map((agent) => {
            const isSource = edges.some((e) => e.from === agent.id)
            const isTarget = edges.some((e) => e.to === agent.id)
            const sc = statusConfig[agent.status]
            return (
              <div key={agent.id} className="flex flex-col items-center">
                <div
                  className="flex h-14 w-14 items-center justify-center rounded-full border-2"
                  style={{ background: sc.bg, borderColor: borderColor(agent.status) }}
                >
                  <Bot className="h-6 w-6" style={{ color: sc.color }} />
                </div>
                <p className="mt-2 text-[0.72rem] font-bold" style={{ color: "var(--text-primary)" }}>{agent.name}</p>
                <span
                  className="inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[0.55rem] font-semibold mt-0.5"
                  style={{ color: sc.color, background: sc.bg }}
                >
                  <span className="h-1 w-1 rounded-full" style={{ background: sc.dot }} />{agent.status}
                </span>
                {isSource && (
                  <div className="mt-2 space-y-1">
                    {edges.filter((e) => e.from === agent.id).map((e) => {
                      const target = agents.find((a) => a.id === e.to)
                      return (
                        <div key={e.task} className="flex items-center gap-1.5 text-[0.6rem]" style={{ color: "var(--text-secondary)" }}>
                          <ArrowRight className="h-3 w-3" style={{ color: "var(--accent)" }} />
                          <span>{target?.name ?? e.to}</span>
                          <span style={{ color: "var(--text-muted)" }}>({e.task})</span>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function borderColor(status: string): string {
  switch (status) {
    case "running": return "var(--accent)"
    case "idle": return "var(--border)"
    case "failed": return "var(--danger)"
    default: return "var(--border)"
  }
}

function SharedMemoryView({ entries }: { entries: SharedMemoryEntry[] }) {
  return (
    <div className="rounded-[16px] p-6" style={{ border: "1px solid var(--border)", background: "var(--surface)" }}>
      <h3 className="text-[0.85rem] font-bold mb-4 flex items-center gap-2" style={{ color: "var(--text-primary)" }}>
        <Share2 className="h-4 w-4" style={{ color: "var(--accent)" }} /> Shared Memory ({entries.length})
      </h3>
      <div className="space-y-2">
        {entries.map((e) => (
          <div
            key={e.id}
            className="rounded-[10px] p-3 transition-colors hover:bg-[var(--surface-raised)]"
            style={{ border: "1px solid var(--border)" }}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <code
                    className="rounded-[4px] px-1.5 py-0.5 text-[0.65rem] font-mono font-bold"
                    style={{ background: "var(--surface-raised)", color: "var(--accent)" }}
                  >{e.key}</code>
                  <span className="text-[0.6rem]" style={{ color: "var(--text-muted)" }}>from {e.source}</span>
                </div>
                <p className="mt-1 text-[0.75rem]" style={{ color: "var(--text-secondary)" }}>{e.value}</p>
                <div className="flex items-center gap-3 mt-1 text-[0.6rem]" style={{ color: "var(--text-muted)" }}>
                  <span>{new Date(e.updatedAt).toLocaleString()}</span>
                  <span>Accessed {e.accessCount} times</span>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function PerformanceView({ agents }: { agents: Agent[] }) {
  return (
    <div className="rounded-[16px] p-6" style={{ border: "1px solid var(--border)", background: "var(--surface)" }}>
      <h3 className="text-[0.85rem] font-bold mb-4 flex items-center gap-2" style={{ color: "var(--text-primary)" }}>
        <BarChart3 className="h-4 w-4" style={{ color: "var(--accent)" }} /> Agent Performance
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full text-left" aria-label="Agent Performance Table">
          <thead>
            <tr className="text-[0.65rem] font-semibold uppercase" style={{ color: "var(--text-muted)", borderBottom: "1px solid var(--border)" }}>
              <th className="pb-3 pr-4">Agent</th>
              <th className="pb-3 pr-4">Tasks</th>
              <th className="pb-3 pr-4">Success Rate</th>
              <th className="pb-3 pr-4">Memory</th>
              <th className="pb-3 pr-4">Uptime</th>
              <th className="pb-3 pr-4">Status</th>
            </tr>
          </thead>
          <tbody>
            {agents.map((a) => {
              const sc = statusConfig[a.status]
              return (
                <tr key={a.id} className="last:border-0" style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="py-3 pr-4">
                    <div className="flex items-center gap-2">
                      <div className="flex h-7 w-7 items-center justify-center rounded-[8px]" style={{ background: sc.bg }}>
                        <Bot className="h-3.5 w-3.5" style={{ color: sc.color }} />
                      </div>
                      <div>
                        <p className="text-[0.78rem] font-semibold" style={{ color: "var(--text-primary)" }}>{a.name}</p>
                        <p className="text-[0.6rem]" style={{ color: "var(--text-muted)" }}>{a.type}</p>
                      </div>
                    </div>
                  </td>
                  <td className="py-3 pr-4 text-[0.8rem] font-bold" style={{ color: "var(--text-primary)" }}>{a.tasksCompleted}</td>
                  <td className="py-3 pr-4">
                    <div className="flex items-center gap-2">
                      <div className="h-1.5 w-16 rounded-full overflow-hidden" style={{ background: "var(--border)" }}>
                        <div className="h-full rounded-full" style={{ width: `${a.successRate}%`, background: "var(--accent)" }} />
                      </div>
                      <span className="text-[0.7rem] font-bold" style={{ color: "var(--text-primary)" }}>{a.successRate}%</span>
                    </div>
                  </td>
                  <td className="py-3 pr-4">
                    <div className="flex items-center gap-2">
                      <div className="h-1.5 w-12 rounded-full overflow-hidden" style={{ background: "var(--border)" }}>
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${a.memoryUsage}%`,
                            background: a.memoryUsage > 75 ? "var(--warning)" : "var(--accent)",
                          }}
                        />
                      </div>
                      <span className="text-[0.7rem] font-medium" style={{ color: "var(--text-secondary)" }}>{a.memoryUsage}%</span>
                    </div>
                  </td>
                  <td className="py-3 pr-4 text-[0.75rem]" style={{ color: "var(--text-secondary)" }}>{a.uptime}</td>
                  <td className="py-3">
                    <span
                      className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[0.6rem] font-semibold"
                      style={{ color: sc.color, background: sc.bg }}
                    >
                      <span className="h-1.5 w-1.5 rounded-full" style={{ background: sc.dot }} />
                      {a.status}
                    </span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function ArrowRight({ className }: { className?: string }) {
  return <ChevronRight className={className} />
}
