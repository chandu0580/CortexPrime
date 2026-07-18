"use client"

import React, { useState, useMemo } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Brain, Search, GitBranch, BookOpen, BarChart3, Clock,
  FileText, Target, Users, Link2, Layers, Filter,
  ChevronRight, CheckCircle2, Activity, Zap, Globe,
  Database, Sparkles, TrendingUp,
} from "lucide-react"
import CortexShell from "@/components/layout/CortexShell"
import { cn } from "@/utils/cn"
import { stagger, variants } from "@/lib/motion-tokens"

interface KnowledgeNode {
  id: string
  label: string
  type: "concept" | "entity" | "document" | "insight" | "mission"
  description: string
  connections: string[]
  confidence: number
  lastAccessed: string
}

interface MissionHistoryEntry {
  id: string
  title: string
  status: "completed" | "failed" | "running"
  insights: number
  artifacts: number
  date: string
  keyFindings: string[]
}

const mockNodes: KnowledgeNode[] = [
  { id: "n1", label: "Market Trends 2026", type: "concept", description: "Overall market direction and key indicators", connections: ["n2", "n3", "n5"], confidence: 0.92, lastAccessed: "2m ago" },
  { id: "n2", label: "Competitor A", type: "entity", description: "Primary competitor in enterprise AI space", connections: ["n1", "n4"], confidence: 0.88, lastAccessed: "15m ago" },
  { id: "n3", label: "S&P 500 Performance", type: "document", description: "Q2 2026 index performance data", connections: ["n1"], confidence: 0.95, lastAccessed: "30m ago" },
  { id: "n4", label: "Competitor Strategy", type: "insight", description: "Competitor A's new product launch strategy", connections: ["n2", "n5"], confidence: 0.76, lastAccessed: "1h ago" },
  { id: "n5", label: "Q2 Market Intel", type: "mission", description: "Q2 market intelligence mission findings", connections: ["n1", "n4"], confidence: 0.91, lastAccessed: "5m ago" },
]

const mockHistory: MissionHistoryEntry[] = [
  { id: "h1", title: "Q2 Market Intelligence", status: "completed", insights: 12, artifacts: 4, date: "2026-07-15", keyFindings: ["S&P 500 up 1.02%", "NASDAQ tech sector growth", "New AI regulations proposed"] },
  { id: "h2", title: "Competitor Landscape", status: "running", insights: 8, artifacts: 3, date: "2026-07-14", keyFindings: ["Competitor A pricing changes", "Market share shifts"] },
  { id: "h3", title: "Customer Sentiment", status: "completed", insights: 15, artifacts: 5, date: "2026-07-13", keyFindings: ["Satisfaction up 12%", "Support response time improved", "Feature request: API integration"] },
  { id: "h4", title: "Pricing Optimization", status: "failed", insights: 4, artifacts: 2, date: "2026-07-12", keyFindings: ["Data insufficient for model"] },
]

const typeColors: Record<string, React.CSSProperties> = {
  concept: { color: "var(--accent-primary)" },
  entity: { color: "var(--accent-primary)" },
  document: { color: "var(--warning)" },
  insight: { color: "var(--danger)" },
  mission: { color: "var(--success)" },
}

const typeBg: Record<string, React.CSSProperties> = {
  concept: { background: "var(--accent-muted)" },
  entity: { background: "var(--accent-muted)" },
  document: { background: "var(--warning-muted)" },
  insight: { background: "var(--danger-muted)" },
  mission: { background: "var(--success-muted)" },
}

const typeIcons: Record<string, typeof Brain> = {
  concept: Brain,
  entity: Globe,
  document: FileText,
  insight: Sparkles,
  mission: Target,
}

export default function KnowledgeExplorerPage() {
  const [search, setSearch] = useState("")
  const [activeTab, setActiveTab] = useState<"graph" | "search" | "history" | "learning">("graph")
  const [selectedNode, setSelectedNode] = useState<KnowledgeNode | null>(null)

  const tabs = [
    { id: "graph" as const, label: "Knowledge Graph", icon: GitBranch },
    { id: "search" as const, label: "Search", icon: Search },
    { id: "history" as const, label: "Mission History", icon: Clock },
    { id: "learning" as const, label: "Learning", icon: TrendingUp },
  ]

  const searchResults = useMemo(() => {
    if (!search) return []
    const q = search.toLowerCase()
    return mockNodes.filter((n) => n.label.toLowerCase().includes(q) || n.description.toLowerCase().includes(q))
  }, [search])

  return (
    <CortexShell title="Knowledge Explorer" subtitle="Knowledge graph, mission history, learning & relationships">
      <div className="mx-auto max-w-[1600px] space-y-6 p-6">
        <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-[10px]" style={{ background: "var(--accent-muted)" }}>
              <Brain size={18} style={{ color: "var(--accent-primary)" }} />
            </div>
            <div>
              <h1 className="text-[1.3rem] font-extrabold tracking-tight" style={{ color: "var(--text-primary)" }}>Knowledge Explorer</h1>
              <p className="text-[0.75rem]" style={{ color: "var(--text-secondary)" }}>Explore relationships, search across knowledge, review mission history</p>
            </div>
          </div>
        </motion.div>

        <div className="flex items-center gap-1 rounded-[12px] p-1 w-fit" role="tablist" style={{ background: "var(--surface)" }}>
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
                  active ? "shadow-sm" : ""
                )}
                style={{
                  background: active ? "var(--surface)" : "transparent",
                  color: active ? "var(--accent-primary)" : "var(--text-secondary)",
                }}
              >
                <Icon className="h-4 w-4" /> {tab.label}
              </button>
            )
          })}
        </div>

        {activeTab === "graph" && (
          <div role="tabpanel" aria-label="Knowledge Graph" className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_320px]">
            <div className="rounded-[16px] p-6" style={{ border: "1px solid var(--border)", background: "var(--surface)" }}>
              <h3 className="text-[0.85rem] font-bold mb-4" style={{ color: "var(--text-primary)" }}>Knowledge Graph</h3>
              <div className="flex flex-wrap gap-3">
                {mockNodes.map((node) => {
                  const Icon = typeIcons[node.type]
                  return (
                    <motion.button
                      key={node.id}
                      whileHover={{ scale: 1.03 }}
                      onClick={() => setSelectedNode(node)}
                      className="rounded-[12px] p-3 text-left transition-all"
                      style={{
                        border: selectedNode?.id === node.id ? "1px solid var(--accent-primary)" : "1px solid var(--border)",
                        background: selectedNode?.id === node.id ? "var(--accent-muted)" : "var(--surface)",
                      }}
                    >
                      <div className="flex items-center gap-2.5">
                        <div className="flex h-8 w-8 items-center justify-center rounded-[8px]" style={typeBg[node.type]}>
                          <Icon className="h-4 w-4" style={typeColors[node.type]} />
                        </div>
                        <div>
                          <p className="text-[0.78rem] font-semibold" style={{ color: "var(--text-primary)" }}>{node.label}</p>
                          <div className="flex items-center gap-2 text-[0.55rem]" style={{ color: "var(--text-muted)" }}>
                            <span className="capitalize">{node.type}</span>
                            <span className="font-semibold" style={{ color: node.confidence > 0.85 ? "var(--accent-primary)" : "var(--warning)" }}>
                              {(node.confidence * 100).toFixed(0)}%
                            </span>
                          </div>
                        </div>
                      </div>
                      <div className="mt-2 flex flex-wrap gap-1">
                        {node.connections.map((c) => {
                          const conn = mockNodes.find((n) => n.id === c)
                          return conn ? (
                            <span key={c} className="rounded-full px-1.5 py-0.5 text-[0.55rem] font-medium" style={{ background: "var(--surface-raised)", color: "var(--text-secondary)" }}>
                              {conn.label}
                            </span>
                          ) : null
                        })}
                      </div>
                    </motion.button>
                  )
                })}
              </div>
            </div>
            <AnimatePresence mode="wait">
              {selectedNode ? (
                <motion.div key={selectedNode.id} initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 20 }} className="rounded-[16px] p-5" style={{ border: "1px solid var(--border)", background: "var(--surface)" }}>
                  <h3 className="text-[0.85rem] font-bold mb-3" style={{ color: "var(--text-primary)" }}>Node Details</h3>
                  <div className="flex h-10 w-10 items-center justify-center rounded-[10px] mb-3" style={typeBg[selectedNode.type]}>
                    {React.createElement(typeIcons[selectedNode.type], { className: "h-5 w-5", style: typeColors[selectedNode.type] })}
                  </div>
                  <p className="text-[0.9rem] font-bold" style={{ color: "var(--text-primary)" }}>{selectedNode.label}</p>
                  <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[0.6rem] font-semibold mt-1" style={{ ...typeBg[selectedNode.type], ...typeColors[selectedNode.type] }}>
                    {selectedNode.type}
                  </span>
                  <p className="mt-3 text-[0.75rem]" style={{ color: "var(--text-secondary)" }}>{selectedNode.description}</p>
                  <div className="mt-4 space-y-2">
                    <div className="flex justify-between text-[0.7rem]">
                      <span style={{ color: "var(--text-muted)" }}>Confidence</span>
                      <span className="font-bold" style={{ color: "var(--text-primary)" }}>{(selectedNode.confidence * 100).toFixed(0)}%</span>
                    </div>
                    <div className="h-1.5 w-full rounded-full overflow-hidden" style={{ background: "var(--border)" }}>
                      <div className="h-full rounded-full" style={{ width: `${selectedNode.confidence * 100}%`, background: "var(--accent-primary)" }} />
                    </div>
                    <div className="flex justify-between text-[0.7rem] mt-2">
                      <span style={{ color: "var(--text-muted)" }}>Last Accessed</span>
                      <span className="font-medium" style={{ color: "var(--text-secondary)" }}>{selectedNode.lastAccessed}</span>
                    </div>
                    <div className="flex justify-between text-[0.7rem]">
                      <span style={{ color: "var(--text-muted)" }}>Connections</span>
                      <span className="font-medium" style={{ color: "var(--text-secondary)" }}>{selectedNode.connections.length}</span>
                    </div>
                  </div>
                </motion.div>
              ) : (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col items-center justify-center py-12 text-center rounded-[16px] border border-dashed" style={{ borderColor: "var(--border)", background: "var(--surface)" }}>
                  <Link2 className="h-10 w-10 mb-3" style={{ color: "var(--text-muted)" }} />
                  <p className="text-[0.8rem] font-semibold" style={{ color: "var(--text-secondary)" }}>Select a node</p>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}

        {activeTab === "search" && (
          <div role="tabpanel" aria-label="Search" className="rounded-[16px] p-6" style={{ border: "1px solid var(--border)", background: "var(--surface)" }}>
            <div className="relative max-w-md mb-6">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" style={{ color: "var(--text-muted)" }} />
              <input
                aria-label="Search knowledge base"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search knowledge base..."
                className="h-10 w-full rounded-[12px] pl-10 pr-4 text-[0.85rem] outline-none placeholder:text-[var(--text-muted)] focus:border-[var(--accent-muted)]"
                style={{
                  border: "1px solid var(--border)",
                  background: "var(--background)",
                  color: "var(--text-primary)",
                }}
              />
            </div>
            {searchResults.length === 0 && search && (
              <div className="flex flex-col items-center py-8 text-center">
                <Search className="h-10 w-10 mb-3" style={{ color: "var(--text-muted)" }} />
                <p className="text-[0.85rem] font-semibold" style={{ color: "var(--text-secondary)" }}>No results for &quot;{search}&quot;</p>
              </div>
            )}
            {searchResults.map((node) => {
              const Icon = typeIcons[node.type]
              return (
                <div key={node.id} className="flex items-center gap-3 rounded-[10px] p-3 mb-2 transition-colors hover:bg-[var(--surface-raised)]" style={{ border: "1px solid var(--border)", background: "var(--surface)" }}>
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[8px]" style={typeBg[node.type]}>
                    <Icon className="h-4 w-4" style={typeColors[node.type]} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-[0.8rem] font-semibold" style={{ color: "var(--text-primary)" }}>{node.label}</p>
                    <p className="text-[0.68rem]" style={{ color: "var(--text-secondary)" }}>{node.description}</p>
                  </div>
                  <span className="text-[0.65rem] font-bold" style={{ color: node.confidence > 0.85 ? "var(--accent-primary)" : "var(--warning)" }}>
                    {(node.confidence * 100).toFixed(0)}%
                  </span>
                </div>
              )
            })}
          </div>
        )}

        {activeTab === "history" && (
          <div role="tabpanel" aria-label="Mission History" className="grid gap-4 sm:grid-cols-2">
            {mockHistory.map((entry) => (
              <div key={entry.id} className="rounded-[16px] p-5" style={{ border: "1px solid var(--border)", background: "var(--surface)" }}>
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2.5">
                    <div className="flex h-8 w-8 items-center justify-center rounded-[8px]" style={{
                      background: entry.status === "completed" ? "var(--accent-muted)" : entry.status === "running" ? "var(--accent-muted)" : "var(--danger-muted)",
                    }}>
                      {entry.status === "completed" ? <CheckCircle2 className="h-4 w-4" style={{ color: "var(--accent-primary)" }} /> :
                       entry.status === "running" ? <Activity className="h-4 w-4" style={{ color: "var(--accent-primary)" }} /> :
                       <Activity className="h-4 w-4" style={{ color: "var(--danger)" }} />}
                    </div>
                    <div>
                      <p className="text-[0.85rem] font-bold" style={{ color: "var(--text-primary)" }}>{entry.title}</p>
                      <p className="text-[0.65rem]" style={{ color: "var(--text-muted)" }}>{entry.date} &middot; {entry.insights} insights &middot; {entry.artifacts} artifacts</p>
                    </div>
                  </div>
                  <span className="rounded-full px-2 py-0.5 text-[0.55rem] font-semibold capitalize" style={{
                    background: entry.status === "completed" ? "var(--accent-muted)" : entry.status === "running" ? "var(--accent-muted)" : "var(--danger-muted)",
                    color: entry.status === "completed" ? "var(--accent-primary)" : entry.status === "running" ? "var(--accent-primary)" : "var(--danger)",
                  }}>{entry.status}</span>
                </div>
                <div className="mt-3 space-y-1">
                  {entry.keyFindings.map((f, i) => (
                    <div key={i} className="flex items-start gap-2 text-[0.7rem]" style={{ color: "var(--text-secondary)" }}>
                      <span className="mt-0.5" style={{ color: "var(--accent-primary)" }}>&#8226;</span>
                      <span>{f}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {activeTab === "learning" && (
          <div role="tabpanel" aria-label="Learning" className="rounded-[16px] p-6" style={{ border: "1px solid var(--border)", background: "var(--surface)" }}>
            <h3 className="text-[0.85rem] font-bold mb-4 flex items-center gap-2" style={{ color: "var(--text-primary)" }}>
              <TrendingUp className="h-4 w-4" style={{ color: "var(--accent-primary)" }} /> Learning Insights
            </h3>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {[
                { title: "Pattern Recognition", description: "Identified 3 recurring market patterns from mission history", impact: "high", category: "Insights" },
                { title: "Knowledge Gaps", description: "Missing data in competitor pricing analysis", impact: "medium", category: "Gaps" },
                { title: "Relationship Discovery", description: "New correlation found between market trends and customer sentiment", impact: "high", category: "Relationships" },
                { title: "Memory Optimization", description: "12 redundant entries identified for cleanup", impact: "low", category: "Optimization" },
                { title: "Cross-Reference", description: "Q2 insights linked to 3 previous missions", impact: "medium", category: "Connections" },
                { title: "Confidence Growth", description: "Average knowledge confidence up 4.2% this week", impact: "high", category: "Metrics" },
              ].map((item, i) => (
                <div key={i} className="rounded-[12px] p-4 transition-shadow" style={{ border: "1px solid var(--border)", background: "var(--surface)" }}>
                  <div className="inline-flex rounded-full px-2 py-0.5 text-[0.55rem] font-semibold mb-2" style={{
                    background: item.impact === "high" ? "var(--accent-muted)" : item.impact === "medium" ? "var(--warning-muted)" : "var(--surface-raised)",
                    color: item.impact === "high" ? "var(--accent-primary)" : item.impact === "medium" ? "var(--warning)" : "var(--text-muted)",
                  }}>{item.impact}</div>
                  <p className="text-[0.78rem] font-bold" style={{ color: "var(--text-primary)" }}>{item.title}</p>
                  <p className="text-[0.68rem] mt-1" style={{ color: "var(--text-secondary)" }}>{item.description}</p>
                  <span className="text-[0.6rem] mt-2 block" style={{ color: "var(--text-muted)" }}>{item.category}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </CortexShell>
  )
}
