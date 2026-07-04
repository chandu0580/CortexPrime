"use client"

import { useState, useMemo, useCallback } from "react"
import { motion } from "framer-motion"
import { SECTIONS, type SectionId } from "./content"
import { cn } from "@/utils/cn"
import { stagger, variants } from "@/lib/motion-tokens"
import {
  Search, Menu, X, ChevronRight, ChevronDown, BookOpen,
  FileText, Code, Terminal, ExternalLink, Sun, Moon,
  ChevronLeft, Home, Sparkles, ArrowRight, Copy, Check,
} from "lucide-react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { SECTION_CONTENT } from "./content"

export function PortalSidebar({ collapsed, onCollapse }: { collapsed: boolean; onCollapse: () => void }) {
  const pathname = usePathname()
  const currentSection = pathname.split("/").pop() as SectionId | undefined

  return (
    <aside className={cn(
      "fixed inset-y-0 left-0 z-40 flex flex-col border-r border-[#E8EDF3] bg-white transition-all duration-300",
      collapsed ? "w-[60px]" : "w-[220px]"
    )}>
      <div className={cn("flex items-center gap-2 px-4 py-[18px] border-b border-[#E8EDF3]", collapsed && "justify-center px-2")}>
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px] bg-gradient-to-br from-[#38B88A] to-[#2F9F77]">
          <BookOpen className="h-4 w-4 text-white" />
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <p className="text-[0.82rem] font-bold leading-tight text-[#111827]">Developer Portal</p>
            <p className="text-[0.62rem] font-medium text-[#9CA3AF]">SDK & Documentation</p>
          </div>
        )}
      </div>

      <div className={cn("px-2 py-2", collapsed && "px-1")}>
        <Link href="/developer-portal"
          className={cn(
            "flex items-center gap-2 rounded-[10px] px-2.5 py-2 text-[0.78rem] font-semibold transition-all",
            !currentSection
              ? "bg-[#ECFBF4] text-[#2F9F77]" : "text-[#6B7280] hover:bg-[#F5F7FA]",
            collapsed && "justify-center px-0"
          )}>
          <Home className="h-4 w-4 shrink-0" />
          {!collapsed && <span>Home</span>}
        </Link>
      </div>

      <nav className="flex-1 overflow-y-auto px-2 py-1 space-y-[1px]">
        {SECTIONS.map((section) => {
          const isActive = currentSection === section.id
          return (
            <Link key={section.id} href={`/developer-portal/${section.id}`}
              className={cn(
                "flex items-center gap-2.5 rounded-[10px] px-2.5 py-2 text-[0.78rem] font-medium transition-all",
                isActive ? "bg-[#ECFBF4] text-[#2F9F77]" : "text-[#6B7280] hover:bg-[#F5F7FA] hover:text-[#111827]",
                collapsed && "justify-center px-0"
              )}>
              <span className="text-base shrink-0">{section.icon}</span>
              {!collapsed && (
                <span className="truncate">{section.label}</span>
              )}
            </Link>
          )
        })}
      </nav>

      <div className="px-2 pb-4 border-t border-[#E8EDF3] pt-2">
        <button onClick={onCollapse} className={cn(
          "flex w-full items-center gap-2 rounded-[10px] border border-[#E8EDF3] bg-white px-2.5 py-1.5 text-[0.72rem] font-semibold text-[#6B7280] hover:bg-[#F5F7FA]",
          collapsed && "justify-center"
        )}>
          <ChevronLeft className={cn("h-3.5 w-3.5 transition-transform", collapsed && "rotate-180")} />
          {!collapsed && <span>Collapse</span>}
        </button>
      </div>
    </aside>
  )
}

export function PortalTopBar({ sidebarWidth, onToggleSearch }: { sidebarWidth: number; onToggleSearch?: () => void }) {
  return (
    <header className="fixed top-0 right-0 z-30 flex items-center gap-3 border-b border-[#E8EDF3] bg-white/96 px-5 py-2.5 backdrop-blur transition-all duration-300"
      style={{ left: sidebarWidth }}>
      <button onClick={onToggleSearch}
        className="flex h-9 w-9 items-center justify-center rounded-[10px] border border-[#E8EDF3] text-[#6B7280] hover:bg-[#F5F7FA]">
        <Search className="h-4 w-4" />
      </button>
      <div className="relative flex-1 max-w-md">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#9CA3AF]" />
        <input
          id="portal-search"
          placeholder="Search documentation, APIs, SDKs..."
          className="h-9 w-full rounded-[10px] border border-[#E8EDF3] bg-[#F5F7FA] pl-9 pr-4 text-[0.8rem] text-[#111827] outline-none placeholder:text-[#9CA3AF] focus:border-[#B7E5D3]"
        />
      </div>
      <div className="ml-auto flex items-center gap-2">
        <Link href="/enterprise-replay"
          className="flex items-center gap-1.5 rounded-[10px] border border-[#E8EDF3] bg-white px-3 py-1.5 text-[0.72rem] font-semibold text-[#6B7280] hover:bg-[#F5F7FA]">
          <ExternalLink className="h-3.5 w-3.5" /> Replay Center
        </Link>
        <Link href="/command"
          className="flex items-center gap-1.5 rounded-[10px] bg-[#38B88A] px-3 py-1.5 text-[0.72rem] font-semibold text-white hover:bg-[#2F9F77]">
          Console
        </Link>
      </div>
    </header>
  )
}

export function SearchOverlay({ onClose }: { onClose: () => void }) {
  const [query, setQuery] = useState("")
  const results = useMemo(() => {
    if (!query.trim()) return []
    const q = query.toLowerCase()
    return SECTIONS.filter((s) =>
      s.label.toLowerCase().includes(q) ||
      s.description.toLowerCase().includes(q) ||
      s.id.includes(q)
    )
  }, [query])

  return (
    <div className="fixed inset-0 z-50 bg-black/20 backdrop-blur-sm" onClick={onClose}>
      <div className="mx-auto mt-[10vh] max-w-2xl px-4" onClick={(e) => e.stopPropagation()}>
        <div className="rounded-[18px] border border-[#E8EDF3] bg-white shadow-xl overflow-hidden">
          <div className="flex items-center gap-3 px-5 py-3 border-b border-[#E8EDF3]">
            <Search className="h-5 w-5 text-[#9CA3AF]" />
            <input value={query} onChange={(e) => setQuery(e.target.value)}
              placeholder="Search documentation..."
              className="flex-1 text-[0.9rem] outline-none text-[#111827] placeholder:text-[#9CA3AF]"
              autoFocus />
            <button onClick={onClose} className="text-[0.7rem] font-semibold text-[#9CA3AF] bg-[#F5F7FA] px-2 py-1 rounded-[6px] border border-[#E8EDF3]">ESC</button>
          </div>
          <div className="max-h-[50vh] overflow-y-auto p-2">
            {results.length === 0 && query.trim() && (
              <p className="text-center py-8 text-[0.82rem] text-[#9CA3AF]">No results found</p>
            )}
            {results.map((section) => (
              <Link key={section.id} href={`/developer-portal/${section.id}`} onClick={onClose}
                className="flex items-center gap-3 p-3 rounded-[10px] hover:bg-[#F5F7FA] transition-colors">
                <span className="text-xl">{section.icon}</span>
                <div className="flex-1">
                  <p className="text-[0.82rem] font-semibold text-[#111827]">{section.label}</p>
                  <p className="text-[0.7rem] text-[#6B7280]">{section.description}</p>
                </div>
                <ChevronRight className="h-4 w-4 text-[#9CA3AF]" />
              </Link>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

export function CodeBlock({ code, lang = "typescript" }: { code: string; lang?: string }) {
  const [copied, setCopied] = useState(false)
  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }, [code])

  return (
    <div className="relative group rounded-[12px] overflow-hidden border border-[#E8EDF3] bg-[#1A1A2E] my-3">
      <div className="flex items-center justify-between px-4 py-2 bg-[#16162A] border-b border-[#2A2A4A]">
        <span className="text-[0.68rem] font-medium text-[#8B8B9E] uppercase tracking-wider">{lang}</span>
        <button onClick={handleCopy}
          className="flex items-center gap-1.5 text-[0.68rem] font-medium text-[#8B8B9E] hover:text-white transition-colors px-2 py-1 rounded-[6px] hover:bg-[#2A2A4A]">
          {copied ? <Check className="h-3.5 w-3.5 text-[#38B88A]" /> : <Copy className="h-3.5 w-3.5" />}
          {copied ? "Copied!" : "Copy"}
        </button>
      </div>
      <pre className="p-4 overflow-x-auto">
        <code className="text-[0.78rem] leading-relaxed text-[#E4E4F0] font-mono whitespace-pre">{code}</code>
      </pre>
    </div>
  )
}

export function MarkdownRenderer({ content }: { content: string }) {
  const lines = content.split("\n")
  const elements: React.ReactNode[] = []
  let inCodeBlock = false
  let codeBlockContent = ""
  let codeBlockLang = ""
  let listItems: React.ReactNode[] = []
  let inTable = false
  let tableContent: React.ReactNode[] = []

  const flushList = () => {
    if (listItems.length > 0) {
      elements.push(
        <ul key={`ul-${elements.length}`} className="space-y-1.5 my-3">
          {listItems}
        </ul>
      )
      listItems = []
    }
  }

  const flushTable = () => {
    if (tableContent.length > 0) {
      elements.push(
        <div key={`table-${elements.length}`} className="overflow-x-auto my-4 rounded-[12px] border border-[#E8EDF3]">
          <table className="w-full text-[0.78rem]">
            {tableContent}
          </table>
        </div>
      )
      tableContent = []
    }
  }

  lines.forEach((line, i) => {
    if (line.startsWith("```")) {
      if (inCodeBlock) {
        elements.push(
          <CodeBlock key={`code-${elements.length}`} code={codeBlockContent.trimEnd()} lang={codeBlockLang} />
        )
        codeBlockContent = ""
        codeBlockLang = ""
        inCodeBlock = false
      } else {
        flushList()
        flushTable()
        inCodeBlock = true
        codeBlockLang = line.slice(3).trim()
      }
      return
    }

    if (inCodeBlock) {
      codeBlockContent += line + "\n"
      return
    }

    flushList()
    flushTable()

    if (line.startsWith("## ")) {
      elements.push(
        <h2 key={`h2-${i}`} className="text-[1.2rem] font-bold text-[#111827] mt-8 mb-3">{line.slice(3)}</h2>
      )
    } else if (line.startsWith("### ")) {
      elements.push(
        <h3 key={`h3-${i}`} className="text-[1rem] font-bold text-[#111827] mt-6 mb-2">{line.slice(4)}</h3>
      )
    } else if (line.startsWith("#### ")) {
      elements.push(
        <h4 key={`h4-${i}`} className="text-[0.9rem] font-bold text-[#111827] mt-4 mb-2">{line.slice(5)}</h4>
      )
    } else if (line.startsWith("---")) {
      elements.push(<hr key={`hr-${i}`} className="my-6 border-[#E8EDF3]" />)
    } else if (line.startsWith("| ")) {
      const cells = line.split("|").filter(Boolean).map((c) => c.trim())
      if (line.includes("---")) return
      if (!inTable) {
        inTable = true
        tableContent.push(
          <thead key={`thead-${i}`}>
            <tr className="border-b border-[#E8EDF3] bg-[#F8FAFC]">
              {cells.map((c, ci) => (
                <th key={ci} className="px-4 py-2.5 text-left text-[0.72rem] font-semibold text-[#6B7280]">{c}</th>
              ))}
            </tr>
          </thead>
        )
      } else {
        tableContent.push(
          <tr key={`tr-${i}`} className="border-b border-[#E8EDF3] last:border-0">
            {cells.map((c, ci) => (
              <td key={ci} className="px-4 py-2.5 text-[0.74rem] text-[#6B7280]">{c}</td>
            ))}
          </tr>
        )
      }
    } else if (line.startsWith("- ")) {
      listItems.push(
        <li key={`li-${i}`} className="flex items-start gap-2 text-[0.82rem] text-[#6B7280]">
          <span className="h-1.5 w-1.5 rounded-full bg-[#38B88A] mt-2 shrink-0" />
          <span>{line.slice(2)}</span>
        </li>
      )
    } else if (line.trim() === "") {
      elements.push(<div key={`spacer-${i}`} className="h-2" />)
    } else {
      elements.push(
        <p key={`p-${i}`} className="text-[0.82rem] leading-relaxed text-[#6B7280] my-2">{line}</p>
      )
    }
  })

  if (inCodeBlock) {
    elements.push(
      <CodeBlock key={`code-${elements.length}`} code={codeBlockContent.trimEnd()} lang={codeBlockLang} />
    )
  }
  flushList()
  flushTable()

  return <div className="prose-cortex">{elements}</div>
}

export function SectionPage({ sectionId }: { sectionId: SectionId }) {
  const content = SECTION_CONTENT[sectionId]

  if (!content) {
    return (
      <div className="text-center py-20">
        <p className="text-[1rem] text-[#6B7280]">Section not found</p>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-[1.8rem] font-bold tracking-[-0.02em] text-[#111827]">{content.title}</h1>
        <p className="mt-1.5 text-[0.9rem] text-[#6B7280]">{content.subtitle}</p>
      </div>

      {content.interactive ? (
        <InteractiveSection sectionId={sectionId} />
      ) : (
        <>
          <MarkdownRenderer content={content.markdown} />
          {content.codeExamples && content.codeExamples.length > 0 && (
            <div className="mt-8">
              <h3 className="text-[1rem] font-bold text-[#111827] mb-4">Code Examples</h3>
              <div className="space-y-4">
                {content.codeExamples.map((ex, i) => (
                  <div key={i}>
                    <p className="text-[0.78rem] font-semibold text-[#6B7280] mb-2">{ex.label}</p>
                    <CodeBlock code={ex.code} lang={ex.lang} />
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}

function InteractiveSection({ sectionId }: { sectionId: SectionId }) {
  switch (sectionId) {
    case "architecture-explorer":
      return <ArchitectureExplorer />
    case "rest-api-explorer":
      return <RestApiExplorer />
    case "websocket-explorer":
      return <WebSocketExplorer />
    case "code-playground":
      return <CodePlayground />
    default:
      return <p className="text-[0.9rem] text-[#6B7280]">Interactive content loading...</p>
  }
}

function ArchitectureExplorer() {
  const modules = [
    { id: "runtime", label: "Runtime", icon: "⚡", color: "#38B88A", desc: "Core execution engine that manages agent lifecycle, task distribution, and mission orchestration. Handles all background processing and real-time execution." },
    { id: "workers", label: "Workers", icon: "🤖", color: "#3B82F6", desc: "Browser (Playwright), Voice (Deepgram/ElevenLabs), and Desktop workers for autonomous task execution across environments." },
    { id: "memory", label: "Memory", icon: "🧠", color: "#8B5CF6", desc: "Multi-tier memory: Redis (working), PostgreSQL+pgvector (episodic/semantic), and reflection memory for long-term context." },
    { id: "knowledge-graph", label: "Knowledge Graph", icon: "🕸️", color: "#F59E0B", desc: "Neo4j-backed graph storing entities, relationships, and inference data for cross-session knowledge." },
    { id: "mission-runtime", label: "Mission Runtime", icon: "🎯", color: "#EF4444", desc: "Autonomous mission execution through stages: INIT→PLANNING→RESEARCHING→REASONING→VALIDATING→GENERATING→MEMORY_UPDATE→COMPLETED." },
    { id: "connectors", label: "Connectors", icon: "🔧", color: "#06B6D4", desc: "Pluggable framework for GitHub, Jira, Slack, Teams, ServiceNow, Confluence, Notion, Azure DevOps integrations." },
    { id: "governance", label: "Governance", icon: "🛡️", color: "#EC4899", desc: "Multi-level approval workflows, safety guardrails, policy evaluation, compliance checks, and emergency stop." },
    { id: "security", label: "Security", icon: "🔒", color: "#14B8A6", desc: "RBAC/ABAC authorization, JWT/OAuth authentication, API key management, secrets vault, and audit logging." },
    { id: "observability", label: "Observability", icon: "📊", color: "#F97316", desc: "Prometheus metrics, OpenTelemetry traces, structured logging, Sentry error tracking, and real-time dashboards." },
    { id: "replay", label: "Replay", icon: "⏪", color: "#6366F1", desc: "Dual-layer (Redis+PostgreSQL) event replay for missions, workers, connectors, decisions, memory, and cost analysis." },
    { id: "certification", label: "Certification", icon: "✅", color: "#22C55E", desc: "Production certification suite validating system integrity, security posture, and mission success rates." },
    { id: "event-bus", label: "Event Bus", icon: "🔗", color: "#A855F7", desc: "Channel-based pub/sub event system with 35+ event categories, filtering, routing, history, and metrics." },
  ]

  const [selected, setSelected] = useState<string | null>(null)
  const active = modules.find((m) => m.id === selected)

  return (
    <div className="space-y-6">
      <p className="text-[0.82rem] text-[#6B7280]">Click any module to view its purpose, dependencies, lifecycle, and public APIs.</p>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
        {modules.map((mod) => (
          <motion.button
            key={mod.id}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => setSelected(selected === mod.id ? null : mod.id)}
            className="rounded-[14px] border-2 p-4 text-left transition-all"
            style={{
              borderColor: selected === mod.id ? mod.color : "#E8EDF3",
              background: selected === mod.id ? `${mod.color}08` : "#FFFFFF",
            }}>
            <div className="flex items-center gap-2.5 mb-2">
              <span className="text-xl">{mod.icon}</span>
              <span className="text-[0.82rem] font-bold text-[#111827]">{mod.label}</span>
            </div>
            <div className="h-1 rounded-full" style={{ background: mod.color, width: "60%" }} />
          </motion.button>
        ))}
      </div>

      {active && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-[18px] border-2 p-6"
          style={{ borderColor: `${active.color}30`, background: `${active.color}06` }}>
          <div className="flex items-center gap-3 mb-4">
            <span className="text-2xl">{active.icon}</span>
            <div>
              <h3 className="text-[1.1rem] font-bold text-[#111827]">{active.label}</h3>
              <p className="text-[0.72rem] text-[#6B7280]">Module Details</p>
            </div>
          </div>
          <p className="text-[0.85rem] leading-relaxed text-[#6B7280] mb-4">{active.desc}</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-[0.78rem]">
            <div className="rounded-[12px] bg-white/80 p-4 border border-[#E8EDF3]">
              <p className="font-bold text-[#111827] mb-2">Dependencies</p>
              <ul className="space-y-1 text-[#6B7280]">
                <li>• EventBus for event publishing</li>
                <li>• Redis for state management</li>
                <li>• PostgreSQL for persistence</li>
              </ul>
            </div>
            <div className="rounded-[12px] bg-white/80 p-4 border border-[#E8EDF3]">
              <p className="font-bold text-[#111827] mb-2">Public APIs</p>
              <ul className="space-y-1 text-[#6B7280]">
                <li>• REST endpoints under /api/{active.id}</li>
                <li>• WebSocket events: {active.id}:*</li>
                <li>• SDK: @cortexprime/{active.id}</li>
              </ul>
            </div>
          </div>
        </motion.div>
      )}
    </div>
  )
}

interface ApiEndpoint {
  method: string
  path: string
  description: string
  auth: string
  group: string
}

const API_ENDPOINTS: ApiEndpoint[] = [
  { method: "POST", path: "/api/runtime/execute", description: "Execute a mission", auth: "Bearer JWT", group: "Mission" },
  { method: "GET", path: "/api/runtime/status", description: "Get runtime status", auth: "Bearer JWT", group: "Mission" },
  { method: "GET", path: "/api/runtime/agents", description: "List registered agents", auth: "Bearer JWT", group: "Mission" },
  { method: "GET", path: "/api/runtime/traces", description: "Get execution traces", auth: "Bearer JWT", group: "Mission" },
  { method: "POST", path: "/api/memory/store", description: "Store memory entry", auth: "Bearer JWT", group: "Memory" },
  { method: "POST", path: "/api/memory/search", description: "Search memories", auth: "Bearer JWT", group: "Memory" },
  { method: "GET", path: "/api/memory/status", description: "Memory system status", auth: "Bearer JWT", group: "Memory" },
  { method: "GET", path: "/api/memory/context/{session_id}", description: "Get session context", auth: "Bearer JWT", group: "Memory" },
  { method: "POST", path: "/api/graph/agent", description: "Create/update agent node", auth: "Bearer JWT", group: "Knowledge Graph" },
  { method: "POST", path: "/api/graph/memory", description: "Create/update memory node", auth: "Bearer JWT", group: "Knowledge Graph" },
  { method: "POST", path: "/api/graph/query", description: "Execute Cypher query", auth: "Bearer JWT", group: "Knowledge Graph" },
  { method: "GET", path: "/api/graph/health", description: "Graph health check", auth: "Bearer JWT", group: "Knowledge Graph" },
  { method: "POST", path: "/auth/login", description: "Authenticate user", auth: "None", group: "Security" },
  { method: "POST", path: "/api/security/users", description: "Create user", auth: "Bearer JWT", group: "Security" },
  { method: "GET", path: "/api/security/roles", description: "List roles", auth: "Bearer JWT", group: "Security" },
  { method: "POST", path: "/api/security/api-keys", description: "Create API key", auth: "Bearer JWT", group: "Security" },
  { method: "POST", path: "/governance/approval/request", description: "Request approval", auth: "Bearer JWT", group: "Approvals" },
  { method: "POST", path: "/governance/approval/approve", description: "Approve request", auth: "Bearer JWT", group: "Approvals" },
  { method: "GET", path: "/governance/approval/queue", description: "List approval queue", auth: "Bearer JWT", group: "Approvals" },
  { method: "GET", path: "/api/mission-replay/{execution_id}", description: "Get full replay", auth: "Bearer JWT", group: "Replay" },
  { method: "GET", path: "/api/mission-replay/{execution_id}/timeline", description: "Get replay timeline", auth: "Bearer JWT", group: "Replay" },
  { method: "GET", path: "/api/mission-replay/{execution_id}/graph", description: "Get replay graph", auth: "Bearer JWT", group: "Replay" },
  { method: "GET", path: "/api/enterprise-replay/workers/{execution_id}", description: "Worker replay", auth: "Bearer JWT", group: "Replay" },
  { method: "GET", path: "/api/enterprise-replay/costs/{execution_id}", description: "Cost replay", auth: "Bearer JWT", group: "Replay" },
  { method: "GET", path: "/api/telemetry/runtime", description: "Runtime metrics", auth: "Bearer JWT", group: "Analytics" },
  { method: "GET", path: "/api/telemetry/health", description: "System health", auth: "Bearer JWT", group: "Analytics" },
  { method: "GET", path: "/metrics", description: "Prometheus metrics", auth: "None", group: "Analytics" },
  { method: "POST", path: "/api/approval-center/policies", description: "Create approval policy", auth: "Bearer JWT", group: "Approvals" },
  { method: "POST", path: "/api/browser/execute", description: "Execute browser action", auth: "Bearer JWT", group: "Workers" },
  { method: "POST", path: "/api/voice/start", description: "Start voice session", auth: "Bearer JWT", group: "Workers" },
  { method: "POST", path: "/computer/execute", description: "Execute desktop action", auth: "Bearer JWT", group: "Workers" },
]

function RestApiExplorer() {
  const [search, setSearch] = useState("")
  const [groupFilter, setGroupFilter] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)

  const groups = [...new Set(API_ENDPOINTS.map((e) => e.group))]

  const filtered = API_ENDPOINTS.filter((ep) => {
    if (groupFilter && ep.group !== groupFilter) return false
    if (search) {
      const q = search.toLowerCase()
      return ep.path.toLowerCase().includes(q) || ep.description.toLowerCase().includes(q) || ep.group.toLowerCase().includes(q)
    }
    return true
  })

  const grouped = filtered.reduce<Record<string, ApiEndpoint[]>>((acc, ep) => {
    if (!acc[ep.group]) acc[ep.group] = []
    acc[ep.group].push(ep)
    return acc
  }, {})

  const methodColors: Record<string, string> = {
    GET: "bg-[#ECFBF4] text-[#2F9F77]",
    POST: "bg-[#EFF6FF] text-[#2563EB]",
    PUT: "bg-[#FFFBEB] text-[#B45309]",
    DELETE: "bg-[#FEF2F2] text-[#B91C1C]",
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#9CA3AF]" />
          <input value={search} onChange={(e) => setSearch(e.target.value)}
            placeholder="Search APIs..." className="h-9 w-full rounded-[10px] border border-[#E8EDF3] bg-white pl-9 pr-3 text-[0.75rem] outline-none" />
        </div>
        <div className="flex items-center gap-1 flex-wrap">
          {groups.map((g) => (
            <button key={g} onClick={() => setGroupFilter(groupFilter === g ? null : g)}
              className={cn(
                "px-2.5 py-1 rounded-[8px] text-[0.7rem] font-semibold border transition-colors",
                groupFilter === g ? "border-[#38B88A] bg-[#ECFBF4] text-[#2F9F77]" : "border-[#E8EDF3] text-[#6B7280] hover:bg-[#F5F7FA]"
              )}>
              {g}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-4">
        {Object.entries(grouped).map(([group, endpoints]) => (
          <div key={group} className="rounded-[18px] border border-[#E8EDF3] bg-white overflow-hidden">
            <button onClick={() => setExpanded(expanded === group ? null : group)}
              className="flex items-center justify-between w-full px-5 py-3.5 bg-[#F8FAFC] border-b border-[#E8EDF3]">
              <span className="text-[0.85rem] font-bold text-[#111827]">{group}</span>
              <ChevronDown className={cn("h-4 w-4 text-[#9CA3AF] transition-transform", expanded === group && "rotate-180")} />
            </button>
            {expanded === group && (
              <div className="divide-y divide-[#E8EDF3]">
                {endpoints.map((ep, i) => (
                  <div key={i} className="px-5 py-3 hover:bg-[#F8FAFC] transition-colors">
                    <div className="flex items-center gap-3">
                      <span className={cn("px-2 py-0.5 rounded-[6px] text-[0.65rem] font-bold font-mono", methodColors[ep.method])}>
                        {ep.method}
                      </span>
                      <code className="text-[0.75rem] font-mono text-[#111827] flex-1">{ep.path}</code>
                      <span className="text-[0.65rem] text-[#9CA3AF]">{ep.auth}</span>
                    </div>
                    <p className="text-[0.72rem] text-[#6B7280] mt-1 ml-14">{ep.description}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function WebSocketExplorer() {
  const wsEvents = [
    { group: "Mission Events", events: [
      { type: "mission:started", data: '{"execution_id": "exec-123", "objective": "Research AI trends", "timestamp": "..."}' },
      { type: "mission:completed", data: '{"execution_id": "exec-123", "status": "completed", "duration_ms": 24000}' },
      { type: "mission:failed", data: '{"execution_id": "exec-123", "error": "Agent timeout", "stage": "researching"}' },
    ]},
    { group: "Worker Events", events: [
      { type: "worker:started", data: '{"worker_type": "browser", "session_id": "sess-456", "url": "https://example.com"}' },
      { type: "worker:action", data: '{"worker_type": "browser", "action": "click", "selector": ".btn", "timestamp": "..."}' },
      { type: "worker:completed", data: '{"worker_type": "voice", "duration_ms": 3200, "tokens_used": 450}' },
    ]},
    { group: "Approval Events", events: [
      { type: "approval:requested", data: '{"approval_id": "apr-789", "mission_id": "mission-123", "risk_level": "high"}' },
      { type: "approval:approved", data: '{"approval_id": "apr-789", "approved_by": "user-456", "timestamp": "..."}' },
      { type: "approval:rejected", data: '{"approval_id": "apr-789", "reason": "Budget exceeded", "timestamp": "..."}' },
    ]},
    { group: "Memory Events", events: [
      { type: "memory:stored", data: '{"memory_type": "semantic", "concept": "Transformer Architecture", "embedding_id": "vec-001"}' },
      { type: "memory:retrieved", data: '{"memory_type": "episodic", "session_id": "sess-456", "count": 5}' },
      { type: "memory:consolidated", data: '{"session_id": "sess-456", "entries_consolidated": 12}' },
    ]},
    { group: "Connector Events", events: [
      { type: "connector:called", data: '{"connector": "github", "endpoint": "/repos/cortexprime/cortexprime/issues", "method": "GET"}' },
      { type: "connector:completed", data: '{"connector": "slack", "status": 200, "duration_ms": 340}' },
      { type: "connector:failed", data: '{"connector": "jira", "error": "Rate limited", "retry_count": 2}' },
    ]},
    { group: "Replay Events", events: [
      { type: "replay:recorded", data: '{"execution_id": "exec-123", "event_count": 42, "store": "redis+postgres"}' },
      { type: "replay:exported", data: '{"execution_id": "exec-123", "format": "json", "event_count": 42}' },
    ]},
  ]

  const [expanded, setExpanded] = useState<string>("Mission Events")

  return (
    <div className="space-y-5">
      <p className="text-[0.82rem] text-[#6B7280]">Connect to the WebSocket at <code className="text-[#38B88A] font-mono text-[0.78rem]">ws://localhost:8000/ws</code> with your JWT token.</p>

      <CodeBlock code={`const ws = new WebSocket("ws://localhost:8000/ws?token=YOUR_JWT_TOKEN");

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log("Event:", data.type, data);
};

ws.onopen = () => {
  ws.send(JSON.stringify({
    type: "subscribe",
    channels: ["mission:*", "worker:*", "memory:*"]
  }));
};`} lang="typescript" />

      <div className="space-y-3">
        {wsEvents.map((group) => (
          <div key={group.group} className="rounded-[18px] border border-[#E8EDF3] bg-white overflow-hidden">
            <button onClick={() => setExpanded(expanded === group.group ? "" : group.group)}
              className="flex items-center justify-between w-full px-5 py-3.5 bg-[#F8FAFC]">
              <span className="text-[0.85rem] font-bold text-[#111827]">{group.group}</span>
              <ChevronDown className={cn("h-4 w-4 text-[#9CA3AF] transition-transform", expanded === group.group && "rotate-180")} />
            </button>
            {expanded === group.group && (
              <div className="divide-y divide-[#E8EDF3]">
                {group.events.map((evt, i) => (
                  <div key={i} className="px-5 py-3">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="h-2 w-2 rounded-full bg-[#38B88A]" />
                      <code className="text-[0.75rem] font-mono font-semibold text-[#111827]">{evt.type}</code>
                    </div>
                    <CodeBlock code={evt.data} lang="json" />
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function CodePlayground() {
  const [selectedLang, setSelectedLang] = useState<string>("all")
  const [selectedTopic, setSelectedTopic] = useState<string>("mission")

  const languages = ["all", "python", "typescript", "bash", "yaml"]
  const topics = [
    { id: "mission", label: "Mission API", icon: "🎯" },
    { id: "worker", label: "Worker API", icon: "🤖" },
    { id: "connector", label: "Connector API", icon: "🔧" },
    { id: "memory", label: "Memory API", icon: "🧠" },
    { id: "graph", label: "Knowledge Graph", icon: "🕸️" },
    { id: "auth", label: "Authentication", icon: "🔒" },
    { id: "replay", label: "Replay API", icon: "⏪" },
    { id: "deploy", label: "Deployment", icon: "📦" },
  ]

  const playgroundCode: Record<string, Record<string, string>> = {
    mission: {
      python: `import requests

# Execute a mission
resp = requests.post(
    "http://localhost:8000/api/runtime/execute",
    json={"objective": "Research AI trends and summarize"},
    headers={"Authorization": f"Bearer {token}"}
)
exec_id = resp.json()["execution_id"]

# Check status
resp = requests.get(
    f"http://localhost:8000/api/runtime/status?execution_id={exec_id}",
    headers={"Authorization": f"Bearer {token}"}
)
print(resp.json())`,
      typescript: `const res = await fetch('/api/runtime/execute', {
  method: 'POST',
  headers: {
    'Authorization': \`Bearer \${token}\`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    objective: 'Research AI trends'
  })
});
const { execution_id } = await res.json();`,
      bash: `curl -X POST http://localhost:8000/api/runtime/execute \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"objective": "Research AI trends"}'`,
      yaml: `# Mission Definition
mission_id: custom-research
name: Custom Research Mission
category: knowledge_discovery
workers: [browser]
governance: standard
stages: [planning, researching, reasoning, generating]`,
    },
    worker: {
      python: `# Browser worker usage via API
import requests

resp = requests.post(
    "http://localhost:8000/api/browser/execute",
    json={
        "action": "navigate",
        "url": "https://example.com",
        "wait_until": "networkidle"
    },
    headers={"Authorization": f"Bearer {token}"}
)
print(resp.json())`,
      typescript: `import { BrowserWorker } from '@/browser-worker/BrowserWorker';

const browser = new BrowserWorker();
await browser.start();
await browser.navigate('https://example.com');
const text = await browser.extract('h1');
console.log('Heading:', text);
await browser.stop();`,
    },
    connector: {
      python: `# Connector usage via API
import requests

resp = requests.post(
    "http://localhost:8000/api/connector/github/execute",
    json={
        "action": "get_issues",
        "params": {"repo": "cortexprime/cortexprime", "state": "open"}
    },
    headers={"Authorization": f"Bearer {token}"}
)
print(resp.json())`,
      typescript: `import { AbstractConnector } from '@/connector-framework/AbstractConnector';

class MyConnector extends AbstractConnector {
  async connect() {
    this.client = new ApiClient({ apiKey: this.config.apiKey });
  }
  async execute(action: string, params: any) {
    return this.client.call(action, params);
  }
}`,
    },
    memory: {
      python: `import requests

# Store memory
resp = requests.post(
    "http://localhost:8000/api/memory/store",
    json={
        "type": "semantic",
        "content": "Transformer architecture uses self-attention",
        "source": "research"
    },
    headers={"Authorization": f"Bearer {token}"}
)

# Search memory
resp = requests.post(
    "http://localhost:8000/api/memory/search",
    json={"query": "transformer architecture", "limit": 5},
    headers={"Authorization": f"Bearer {token}"}
)
print(resp.json())`,
    },
    graph: {
      python: `import requests

# Create a concept node
resp = requests.post(
    "http://localhost:8000/api/graph/concept",
    json={
        "name": "Transformer",
        "domain": "deep_learning",
        "properties": {"year": 2017, "paper": "Attention is All You Need"}
    },
    headers={"Authorization": f"Bearer {token}"}
)

# Run a Cypher query
resp = requests.post(
    "http://localhost:8000/api/graph/query",
    json={"cypher": "MATCH (n) RETURN n LIMIT 10"},
    headers={"Authorization": f"Bearer {token}"}
)`,
    },
    auth: {
      python: `import requests

# Login
resp = requests.post("http://localhost:8000/auth/login", json={
    "username": "admin",
    "password": "your-password"
})
token = resp.json()["access_token"]
print(f"Token: {token[:20]}...")

# Use API key instead
resp = requests.get(
    "http://localhost:8000/api/runtime/status",
    headers={"X-API-Key": "cp_api_live_abc123..."}
)`,
    },
    replay: {
      python: `import requests

# Get full replay
resp = requests.get(
    "http://localhost:8000/api/mission-replay/exec-123",
    headers={"Authorization": f"Bearer {token}"}
)
data = resp.json()
print(f"Events: {data['summary']['total_events']}")

# Get timeline
resp = requests.get(
    "http://localhost:8000/api/mission-replay/exec-123/timeline",
    headers={"Authorization": f"Bearer {token}"}
)

# Export as JSON
resp = requests.get(
    "http://localhost:8000/api/enterprise-replay/export/exec-123?format=json",
    headers={"Authorization": f"Bearer {token}"}
)`,
    },
    deploy: {
      bash: `# Docker Compose
docker compose up -d

# Check status
curl http://localhost:8000/health

# View logs
docker compose logs -f backend

# Scale
docker compose up -d --scale backend=3`,
      yaml: `# docker-compose.prod.yml
version: "3.8"
services:
  backend:
    image: cortexprime/backend:latest
    ports: ["8000:8000"]
    environment:
      - DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/cortex
      - REDIS_URL=redis://redis:6379
    deploy:
      replicas: 3`,
    },
  }

  const currentCode = playgroundCode[selectedTopic]?.[selectedLang === "all" ? "python" : selectedLang] ?? ""

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-2 flex-wrap">
        {topics.map((t) => (
          <button key={t.id} onClick={() => setSelectedTopic(t.id)}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 rounded-[10px] text-[0.75rem] font-semibold border transition-colors",
              selectedTopic === t.id ? "border-[#38B88A] bg-[#ECFBF4] text-[#2F9F77]" : "border-[#E8EDF3] text-[#6B7280] hover:bg-[#F5F7FA]"
            )}>
            <span>{t.icon}</span> {t.label}
          </button>
        ))}
      </div>

      <div className="flex items-center gap-2">
        {languages.map((l) => (
          <button key={l} onClick={() => setSelectedLang(l)}
            className={cn(
              "px-2.5 py-1 rounded-[8px] text-[0.7rem] font-semibold border transition-colors",
              selectedLang === l ? "border-[#3B82F6] bg-[#EFF6FF] text-[#2563EB]" : "border-[#E8EDF3] text-[#6B7280] hover:bg-[#F5F7FA]"
            )}>
            {l === "all" ? "All" : l.charAt(0).toUpperCase() + l.slice(1)}
          </button>
        ))}
      </div>

      {currentCode && <CodeBlock code={currentCode} lang={selectedLang === "all" ? "python" : selectedLang} />}
      {!currentCode && (
        <p className="text-[0.82rem] text-[#9CA3AF] py-8 text-center">
          Select a language to see code examples for {topics.find((t) => t.id === selectedTopic)?.label}
        </p>
      )}
    </div>
  )
}