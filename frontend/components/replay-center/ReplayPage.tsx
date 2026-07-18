"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  ListRestart, Play, Pause, SkipBack, SkipForward, Clock,
  FileText, Activity, Bot, Target, Calendar, BarChart3,
  ChevronLeft, ChevronRight, Filter, Search, Download,
  CheckCircle2, AlertCircle, CircleDot, Loader2, RefreshCw,
  Archive, Globe, Database, Sparkles, Workflow,
} from "lucide-react"
import CortexShell from "@/components/layout/CortexShell"
import { cn } from "@/utils/cn"
import { stagger, variants } from "@/lib/motion-tokens"

interface ReplaySession {
  id: string
  title: string
  mission: string
  agent: string
  status: "completed" | "running" | "failed"
  duration: string
  actions: number
  date: string
  score: number
}

interface TimelineEvent {
  time: string
  title: string
  detail: string
  type: "session" | "action" | "event" | "artifact"
  status: "completed" | "running" | "failed"
}

interface Artifact {
  name: string
  type: string
  size: string
  created: string
}

const sessions: ReplaySession[] = [
  { id: "S-001", title: "Q2 Market Intelligence", mission: "Market Research", agent: "Research Agent", status: "completed", duration: "24m 18s", actions: 1248, date: "2026-07-15", score: 96 },
  { id: "S-002", title: "Competitor Analysis", mission: "Competitor Landscape", agent: "Data Analyst", status: "completed", duration: "18m 32s", actions: 842, date: "2026-07-15", score: 94 },
  { id: "S-003", title: "Industry Report Generation", mission: "Report Gen", agent: "Report Agent", status: "running", duration: "12m 04s", actions: 456, date: "2026-07-16", score: 88 },
  { id: "S-004", title: "Pricing Strategy Research", mission: "Pricing Analysis", agent: "Finance Agent", status: "failed", duration: "15m 04s", actions: 512, date: "2026-07-14", score: 42 },
  { id: "S-005", title: "Customer Insights Mining", mission: "Customer Research", agent: "Data Analyst", status: "completed", duration: "21m 47s", actions: 1103, date: "2026-07-14", score: 97 },
]

const timelineEvents: TimelineEvent[] = [
  { time: "10:30:02", title: "Session Started", detail: "Research Agent initialized", type: "session", status: "completed" },
  { time: "10:30:04", title: "Planner Started", detail: "Mission plan generated", type: "action", status: "completed" },
  { time: "10:30:09", title: "Memory Retrieved", detail: "Context loaded from shared memory", type: "event", status: "completed" },
  { time: "10:31:12", title: "Browser Opened", detail: "Navigated to bloomberg.com/markets", type: "action", status: "completed" },
  { time: "10:34:18", title: "Data Extracted", detail: "Market indices extracted", type: "artifact", status: "completed" },
  { time: "10:41:16", title: "Research Completed", detail: "Analysis complete, generating insights", type: "action", status: "completed" },
  { time: "10:48:22", title: "Insight Generated", detail: "Key findings summarized", type: "artifact", status: "completed" },
  { time: "10:52:00", title: "Report Created", detail: "Final report drafted", type: "artifact", status: "completed" },
  { time: "10:54:18", title: "Session Completed", detail: "All actions completed successfully", type: "session", status: "completed" },
]

const artifacts: Artifact[] = [
  { name: "Market Analysis Report.pdf", type: "Report", size: "2.4 MB", created: "2026-07-15" },
  { name: "Competitor Dataset.csv", type: "Dataset", size: "8.1 MB", created: "2026-07-15" },
  { name: "Key Insights.md", type: "Document", size: "0.3 MB", created: "2026-07-15" },
  { name: "Market Chart Export.png", type: "Image", size: "1.2 MB", created: "2026-07-15" },
]

const typeIcons: Record<string, typeof FileText> = { session: Play, action: Activity, event: Clock, artifact: Archive }
const typeColors: Record<string, string> = { session: "var(--accent)", action: "var(--accent)", event: "var(--warning)", artifact: "var(--accent)" }
const typeBg: Record<string, string> = { session: "var(--accent-muted)", action: "var(--surface-raised)", event: "var(--warning-muted)", artifact: "var(--surface-raised)" }

export default function ReplayPage() {
  const [search, setSearch] = useState("")
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(1)
  const [selectedSession, setSelectedSession] = useState<ReplaySession>(sessions[0])
  const [activeTab, setActiveTab] = useState<"timeline" | "events" | "artifacts">("timeline")

  const filteredSessions = sessions.filter((s) =>
    s.title.toLowerCase().includes(search.toLowerCase()) || s.id.toLowerCase().includes(search.toLowerCase())
  )

  const handleSessionKeyDown = (session: ReplaySession) => (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault()
      setSelectedSession(session)
    }
  }

  return (
    <CortexShell title="Replay Center" subtitle="Mission replay, timeline, runtime events & artifacts">
      <div className="mx-auto max-w-[1600px] space-y-6 p-6">
        <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-[var(--radius-sm)]" style={{ background: "var(--accent-muted)" }}>
              <ListRestart size={18} style={{ color: "var(--accent)" }} />
            </div>
            <div>
              <h1 className="text-[1.3rem] font-extrabold tracking-tight" style={{ color: "var(--text-primary)" }}>Replay Center</h1>
              <p className="text-[0.75rem]" style={{ color: "var(--text-secondary)" }}>Review and analyze past agent sessions and actions</p>
            </div>
          </div>
        </motion.div>

        <motion.div variants={stagger(0.04)} initial="hidden" animate="visible" className="grid gap-4 sm:grid-cols-5">
          {[
            { label: "Total Sessions", value: "248", icon: ListRestart, color: "var(--accent)" },
            { label: "Total Actions", value: "12,842", icon: Activity, color: "var(--accent)" },
            { label: "Avg Duration", value: "18m 42s", icon: Clock, color: "var(--accent)" },
            { label: "Success Rate", value: "96.3%", icon: CheckCircle2, color: "var(--accent)" },
            { label: "Errors", value: "52", icon: AlertCircle, color: "var(--danger)" },
          ].map((m) => {
            const Icon = m.icon
            return (
              <div key={m.label} className="rounded-[var(--radius-md)] border p-4" style={{ borderColor: "var(--border)", background: "var(--surface)" }}>
                <div className="flex items-center justify-between">
                  <span className="text-[0.65rem] font-semibold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>{m.label}</span>
                  <Icon className="h-4 w-4" style={{ color: m.color }} />
                </div>
                <p className="mt-1.5 text-[1.3rem] font-extrabold tracking-tight" style={{ color: "var(--text-primary)" }}>{m.value}</p>
              </div>
            )
          })}
        </motion.div>

        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1fr_400px]">
          <div className="space-y-4">
            <div className="relative max-w-xs">
              <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2" style={{ color: "var(--text-muted)" }} />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search sessions..."
                aria-label="Search replay sessions"
                className="h-9 w-full rounded-[var(--radius-sm)] border bg-[var(--surface)] pl-9 pr-3 text-[0.8rem] outline-none placeholder:text-[var(--text-muted)] focus:border-[var(--accent-muted)]"
                style={{ borderColor: "var(--border)" }}
              />
            </div>

            <div className="space-y-2">
              {filteredSessions.length === 0 ? (
                <div className="rounded-[var(--radius-md)] border p-8 text-center" style={{ borderColor: "var(--border)", background: "var(--surface)" }}>
                  <p className="text-[0.85rem] font-semibold" style={{ color: "var(--text-secondary)" }}>No sessions match your search</p>
                </div>
              ) : (
                filteredSessions.map((session) => {
                  const isSelected = selectedSession?.id === session.id
                  return (
                    <motion.div
                      key={session.id}
                      layout
                      onClick={() => setSelectedSession(session)}
                      onKeyDown={handleSessionKeyDown(session)}
                      role="button"
                      tabIndex={0}
                      aria-pressed={isSelected}
                      className={cn(
                        "rounded-[var(--radius-md)] border p-4 cursor-pointer transition-all",
                        isSelected ? "shadow-sm" : "hover:shadow-sm"
                      )}
                      style={{
                        borderColor: isSelected ? "var(--accent)" : "var(--border)",
                        background: isSelected ? "var(--accent-muted)" : "var(--surface)",
                      }}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-center gap-3 flex-1 min-w-0">
                          <div
                            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[var(--radius-sm)]"
                            style={{
                              background: session.status === "completed" ? "var(--accent-muted)" : session.status === "running" ? "var(--surface-raised)" : "var(--danger-muted)",
                            }}
                          >
                            {session.status === "completed" ? <CheckCircle2 className="h-4 w-4" style={{ color: "var(--accent)" }} /> :
                             session.status === "running" ? <Loader2 className="h-4 w-4 animate-spin" style={{ color: "var(--accent)" }} /> :
                             <AlertCircle className="h-4 w-4" style={{ color: "var(--danger)" }} />}
                          </div>
                          <div className="min-w-0">
                            <p className="text-[0.82rem] font-bold truncate" style={{ color: "var(--text-primary)" }}>{session.title}</p>
                            <div className="flex items-center gap-2 text-[0.62rem]" style={{ color: "var(--text-muted)" }}>
                              <span>{session.id}</span>
                              <span className="h-3 w-px" style={{ background: "var(--border)" }} />
                              <span>{session.mission}</span>
                              <span className="h-3 w-px" style={{ background: "var(--border)" }} />
                              <span>{session.agent}</span>
                            </div>
                          </div>
                        </div>
                        <div className="text-right shrink-0">
                          <span
                            className="text-[0.85rem] font-extrabold"
                            style={{
                              color: session.score >= 90 ? "var(--accent)" : session.score >= 60 ? "var(--warning)" : "var(--danger)",
                            }}
                          >{session.score}%</span>
                        </div>
                      </div>
                      <div className="mt-2 flex items-center gap-3 text-[0.65rem]" style={{ color: "var(--text-muted)" }}>
                        <span className="flex items-center gap-1"><Clock className="h-3 w-3" /> {session.duration}</span>
                        <span className="flex items-center gap-1"><Activity className="h-3 w-3" /> {session.actions.toLocaleString()} actions</span>
                        <span className="flex items-center gap-1"><Calendar className="h-3 w-3" /> {session.date}</span>
                      </div>
                    </motion.div>
                  )
                })
              )}
            </div>
          </div>

          <div className="space-y-4">
            <div className="rounded-[var(--radius-md)] border p-5" style={{ borderColor: "var(--border)", background: "var(--surface)" }}>
              <h3 className="text-[0.85rem] font-bold mb-3" style={{ color: "var(--text-primary)" }}>{selectedSession.title}</h3>
              <div className="flex items-center gap-4 mb-4">
                <button
                  onClick={() => setPlaying(!playing)}
                  aria-label={playing ? "Pause" : "Play"}
                  className="flex h-9 w-9 items-center justify-center rounded-full text-white"
                  style={{ background: "var(--accent)" }}
                >
                  {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                </button>
                <div className="flex items-center gap-1" role="group" aria-label="Playback speed">
                  {[0.5, 1, 2, 4].map((s) => (
                    <button
                      key={s}
                      onClick={() => setSpeed(s)}
                      aria-pressed={speed === s}
                      className={cn(
                        "rounded-[var(--radius-sm)] px-2 py-1 text-[0.6rem] font-semibold transition-colors",
                        speed === s ? "text-white" : "hover:bg-[var(--accent-muted)]"
                      )}
                      style={{
                        background: speed === s ? "var(--accent)" : "var(--surface-raised)",
                        color: speed === s ? "white" : "var(--text-secondary)",
                      }}
                    >{s}x</button>
                  ))}
                </div>
                <div className="flex-1">
                  <div className="h-1.5 rounded-full overflow-hidden" style={{ background: "var(--border)" }}>
                    <div className="h-full rounded-full" style={{ background: "var(--accent)", width: "35%" }} />
                  </div>
                </div>
                <span className="text-[0.7rem] font-semibold" style={{ color: "var(--text-secondary)" }}>08:42 / {selectedSession.duration}</span>
              </div>
            </div>

            <div className="flex gap-1 rounded-[var(--radius-sm)] p-1" style={{ background: "var(--surface-raised)" }} role="tablist" aria-label="Session details tabs">
              {(["timeline", "events", "artifacts"] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  role="tab"
                  aria-selected={activeTab === tab}
                  aria-controls={`tabpanel-${tab}`}
                  id={`tab-${tab}`}
                  className={cn(
                    "flex-1 rounded-[var(--radius-sm)] px-3 py-2 text-[0.7rem] font-semibold transition-all capitalize",
                    activeTab === tab ? "shadow-sm" : ""
                  )}
                  style={{
                    background: activeTab === tab ? "var(--surface)" : "transparent",
                    color: activeTab === tab ? "var(--text-primary)" : "var(--text-secondary)",
                  }}
                >{tab}</button>
              ))}
            </div>

            {activeTab === "timeline" && (
              <div
                className="rounded-[var(--radius-md)] border p-5"
                style={{ borderColor: "var(--border)", background: "var(--surface)" }}
                role="tabpanel"
                id="tabpanel-timeline"
                aria-labelledby="tab-timeline"
              >
                <div className="relative space-y-0">
                  {timelineEvents.map((event, i) => {
                    const Icon = typeIcons[event.type]
                    return (
                      <div key={i} className="relative flex gap-4 pb-4 last:pb-0">
                        {i < timelineEvents.length - 1 && <div className="absolute left-[11px] top-6 bottom-0 w-px" style={{ background: "var(--border)" }} />}
                        <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full" style={{ background: typeBg[event.type] }}>
                          <Icon className="h-3 w-3" style={{ color: typeColors[event.type] }} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between">
                            <p className="text-[0.75rem] font-semibold" style={{ color: "var(--text-primary)" }}>{event.title}</p>
                            <span className="text-[0.6rem] font-mono" style={{ color: "var(--text-muted)" }}>{event.time}</span>
                          </div>
                          <p className="text-[0.65rem]" style={{ color: "var(--text-secondary)" }}>{event.detail}</p>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {activeTab === "events" && (
              <div
                className="rounded-[var(--radius-md)] border p-5"
                style={{ borderColor: "var(--border)", background: "var(--surface)" }}
                role="tabpanel"
                id="tabpanel-events"
                aria-labelledby="tab-events"
              >
                <h3 className="text-[0.85rem] font-bold mb-3 flex items-center gap-2" style={{ color: "var(--text-primary)" }}>
                  <Activity className="h-4 w-4" style={{ color: "var(--accent)" }} /> Runtime Events
                </h3>
                <div className="space-y-2">
                  {[
                    { label: "Mission Created", agent: "Supervisor", time: "10:30:02", status: "completed" },
                    { label: "Memory Retrieved", agent: "Memory Agent", time: "10:30:09", status: "completed" },
                    { label: "Browser Opened", agent: "Browser Agent", time: "10:31:12", status: "completed" },
                    { label: "Research Completed", agent: "Research Agent", time: "10:41:16", status: "completed" },
                    { label: "Insight Generated", agent: "Insight Agent", time: "10:48:22", status: "completed" },
                    { label: "Mission Finished", agent: "Supervisor", time: "10:54:18", status: "completed" },
                  ].map((e, i) => (
                    <div key={i} className="flex items-center gap-3 rounded-[var(--radius-sm)] border p-2.5" style={{ borderColor: "var(--border)" }}>
                      <CheckCircle2 className="h-3.5 w-3.5" style={{ color: "var(--accent)" }} />
                      <p className="flex-1 text-[0.72rem] font-medium" style={{ color: "var(--text-primary)" }}>{e.label}</p>
                      <span className="text-[0.6rem]" style={{ color: "var(--text-muted)" }}>{e.agent}</span>
                      <span className="text-[0.6rem] font-mono" style={{ color: "var(--text-muted)" }}>{e.time}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {activeTab === "artifacts" && (
              <div
                className="rounded-[var(--radius-md)] border p-5"
                style={{ borderColor: "var(--border)", background: "var(--surface)" }}
                role="tabpanel"
                id="tabpanel-artifacts"
                aria-labelledby="tab-artifacts"
              >
                <h3 className="text-[0.85rem] font-bold mb-3 flex items-center gap-2" style={{ color: "var(--text-primary)" }}>
                  <Archive className="h-4 w-4" style={{ color: "var(--accent)" }} /> Artifacts ({artifacts.length})
                </h3>
                <div className="space-y-2">
                  {artifacts.map((a) => (
                    <div key={a.name} className="flex items-center gap-3 rounded-[var(--radius-sm)] border p-2.5 transition-colors cursor-pointer bg-[var(--surface)] hover:bg-[var(--surface-raised)]" style={{ borderColor: "var(--border)" }}>
                      <FileText className="h-4 w-4" style={{ color: "var(--accent)" }} />
                      <div className="flex-1 min-w-0">
                        <p className="text-[0.72rem] font-semibold truncate" style={{ color: "var(--text-primary)" }}>{a.name}</p>
                        <div className="flex items-center gap-2 text-[0.6rem]" style={{ color: "var(--text-muted)" }}>
                          <span>{a.type}</span>
                          <span>{a.size}</span>
                          <span>{a.created}</span>
                        </div>
                      </div>
                      <Download className="h-3.5 w-3.5" style={{ color: "var(--text-muted)" }} />
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </CortexShell>
  )
}
