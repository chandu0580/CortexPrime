"use client"

import { useState, useMemo } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { cn } from "@/utils/cn"
import {
  Target,
  ShieldCheck,
  FileText,
  Repeat,
  Database,
  Share2,
  Cpu,
  Plug,
  Search,
  Filter,
  ChevronDown,
  Loader2,
  Activity,
  Users,
  Globe,
  AlertTriangle,
  CheckCircle,
  Clock,
} from "lucide-react"

type Subsystem =
  | "mission"
  | "security"
  | "governance"
  | "replay"
  | "memory"
  | "knowledge_graph"
  | "worker"
  | "connector"

interface ActivityEvent {
  id: string
  subsystem: Subsystem
  icon?: React.ReactNode
  title: string
  description: string
  timestamp: Date
  source: string
}

const subsystemConfig: Record<Subsystem, { label: string; icon: React.ReactNode; color: string }> = {
  mission: { label: "Mission", icon: <Target size={14} />, color: "text-emerald-600 bg-emerald-50 border-emerald-200" },
  security: { label: "Security", icon: <ShieldCheck size={14} />, color: "text-red-600 bg-red-50 border-red-200" },
  governance: { label: "Governance", icon: <FileText size={14} />, color: "text-purple-600 bg-purple-50 border-purple-200" },
  replay: { label: "Replay", icon: <Repeat size={14} />, color: "text-amber-600 bg-amber-50 border-amber-200" },
  memory: { label: "Memory", icon: <Database size={14} />, color: "text-cyan-600 bg-cyan-50 border-cyan-200" },
  knowledge_graph: { label: "Knowledge Graph", icon: <Share2 size={14} />, color: "text-indigo-600 bg-indigo-50 border-indigo-200" },
  worker: { label: "Worker", icon: <Cpu size={14} />, color: "text-slate-600 bg-slate-50 border-slate-200" },
  connector: { label: "Connector", icon: <Plug size={14} />, color: "text-blue-600 bg-blue-50 border-blue-200" },
}

function timeAgo(date: Date): string {
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000)
  if (seconds < 10) return "just now"
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}d ago`
  const months = Math.floor(days / 30)
  return `${months}mo ago`
}

const mockEvents: ActivityEvent[] = [
  { id: "e1", subsystem: "mission", title: "Pipeline extraction completed", description: "Data Pipeline ETL finished processing 2.4M records with zero errors.", timestamp: new Date(Date.now() - 2 * 60 * 1000), source: "etl-pipeline-v2" },
  { id: "e2", subsystem: "security", title: "Brute force attempt blocked", description: "12 rapid login attempts from 198.51.100.7 were automatically throttled.", timestamp: new Date(Date.now() - 5 * 60 * 1000), source: "auth-gateway" },
  { id: "e3", subsystem: "worker", title: "Worker node scaled up", description: "3 GPU workers added to cluster w-asia. Total active: 47.", timestamp: new Date(Date.now() - 8 * 60 * 1000), source: "cluster-autoscaler" },
  { id: "e4", subsystem: "connector", title: "Slack integration synced", description: "12 new channels discovered and linked to workspace #eng.", timestamp: new Date(Date.now() - 15 * 60 * 1000), source: "slack-connector" },
  { id: "e5", subsystem: "memory", title: "Long-term memory consolidated", description: "3,214 episodic memories merged into semantic store.", timestamp: new Date(Date.now() - 22 * 60 * 1000), source: "memory-service" },
  { id: "e6", subsystem: "governance", title: "Compliance report generated", description: "Weekly SOC 2 compliance snapshot generated. 0 violations.", timestamp: new Date(Date.now() - 30 * 60 * 1000), source: "compliance-engine" },
  { id: "e7", subsystem: "knowledge_graph", title: "Entity relationship inferred", description: "New relationship 'reports_to' inferred across 85 employee nodes.", timestamp: new Date(Date.now() - 40 * 60 * 1000), source: "graph-inference" },
  { id: "e8", subsystem: "replay", title: "Session replay encoded", description: "Browser session #4421 encoded and ready for inspection.", timestamp: new Date(Date.now() - 50 * 60 * 1000), source: "replay-worker" },
  { id: "e9", subsystem: "worker", title: "Worker w-022 health check failed", description: "Heartbeat missed for 30s. Auto-remediation triggered.", timestamp: new Date(Date.now() - 60 * 60 * 1000), source: "health-monitor" },
  { id: "e10", subsystem: "mission", title: "Mission 'Nightly Audit' dispatched", description: "Audit mission dispatched to 12 worker nodes across 3 regions.", timestamp: new Date(Date.now() - 75 * 60 * 1000), source: "mission-control" },
  { id: "e11", subsystem: "security", title: "API key rotated", description: "API key sk_live_8f3a... was rotated per schedule. New key active.", timestamp: new Date(Date.now() - 90 * 60 * 1000), source: "key-vault" },
  { id: "e12", subsystem: "connector", title: "GitHub webhook registered", description: "Webhook for repo cortexprime/core registered on push events.", timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000), source: "github-connector" },
  { id: "e13", subsystem: "memory", title: "Memory pruning completed", description: "9,421 stale ephemeral records evicted from short-term store.", timestamp: new Date(Date.now() - 3 * 60 * 60 * 1000), source: "memory-maintenance" },
  { id: "e14", subsystem: "governance", title: "Access policy updated", description: "Role 'viewer' updated: read-only access to 12 new resources.", timestamp: new Date(Date.now() - 4 * 60 * 60 * 1000), source: "policy-service" },
  { id: "e15", subsystem: "knowledge_graph", title: "Graph index rebuilt", description: "Vector index for knowledge graph rebuilt. Recall latency -23%.", timestamp: new Date(Date.now() - 5 * 60 * 60 * 1000), source: "graph-indexer" },
]

const allSubsystems = Object.keys(subsystemConfig) as Subsystem[]
const PAGE_SIZE = 10

const itemVariants = {
  hidden: { opacity: 0, y: 12 } as const,
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.04, type: "spring" as const, damping: 22, stiffness: 220 },
  }),
}

export default function ActivityFeed() {
  const [search, setSearch] = useState("")
  const [activeFilters, setActiveFilters] = useState<Subsystem[]>([])
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE)

  const filteredEvents = useMemo(() => {
    let events = mockEvents

    if (activeFilters.length > 0) {
      events = events.filter((e) => activeFilters.includes(e.subsystem))
    }

    if (search.trim()) {
      const lower = search.toLowerCase()
      events = events.filter(
        (e) =>
          e.title.toLowerCase().includes(lower) ||
          e.description.toLowerCase().includes(lower) ||
          e.source.toLowerCase().includes(lower)
      )
    }

    return events
  }, [activeFilters, search])

  const visibleEvents = useMemo(() => {
    return filteredEvents.slice(0, visibleCount)
  }, [filteredEvents, visibleCount])

  const toggleFilter = (subsystem: Subsystem) => {
    setActiveFilters((prev) =>
      prev.includes(subsystem) ? prev.filter((s) => s !== subsystem) : [...prev, subsystem]
    )
    setVisibleCount(PAGE_SIZE)
  }

  const hasMore = visibleCount < filteredEvents.length

  return (
    <div className="rounded-[18px] border border-[#E8EDF3] bg-white">
      <div className="border-b border-[#E8EDF3] px-5 py-4">
        <div className="mb-3 flex items-center gap-2">
          <Activity size={18} className="text-gray-500" />
          <h2 className="text-[15px] font-semibold text-gray-900">Activity Feed</h2>
        </div>

        <div className="relative mb-3">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value)
              setVisibleCount(PAGE_SIZE)
            }}
            placeholder="Search events..."
            className="w-full rounded-xl border border-[#E8EDF3] bg-gray-50 py-2 pl-9 pr-3 text-[13px] text-gray-900 outline-none placeholder:text-gray-400 focus:border-blue-200 focus:bg-white focus:ring-1 focus:ring-blue-100"
          />
        </div>

        <div className="flex flex-wrap gap-1.5">
          <button
            onClick={() => {
              setActiveFilters([])
              setVisibleCount(PAGE_SIZE)
            }}
            className={cn(
              "flex items-center gap-1 rounded-lg border px-2.5 py-1 text-[11px] font-medium transition-colors",
              activeFilters.length === 0
                ? "border-blue-200 bg-blue-50 text-blue-700"
                : "border-[#E8EDF3] text-gray-500 hover:bg-gray-50"
            )}
          >
            <Filter size={12} />
            All
          </button>
          {allSubsystems.map((sub) => {
            const config = subsystemConfig[sub]
            const isActive = activeFilters.includes(sub)
            return (
              <button
                key={sub}
                onClick={() => toggleFilter(sub)}
                className={cn(
                  "flex items-center gap-1 rounded-lg border px-2.5 py-1 text-[11px] font-medium transition-colors",
                  isActive
                    ? "border-blue-200 bg-blue-50 text-blue-700"
                    : "border-[#E8EDF3] text-gray-500 hover:bg-gray-50"
                )}
              >
                {config.icon}
                {config.label}
              </button>
            )
          })}
        </div>
      </div>

      <div className="max-h-[600px] overflow-y-auto">
        <div className="relative px-5 py-3">
          {visibleEvents.length === 0 ? (
            <div className="flex flex-col items-center py-12 text-gray-400">
              <Search size={28} className="mb-2 opacity-50" />
              <p className="text-sm">No matching events found</p>
            </div>
          ) : (
            <div className="relative">
              <div className="absolute left-[19px] top-2 bottom-2 w-px bg-[#E8EDF3]" />
              <AnimatePresence mode="popLayout">
                {visibleEvents.map((event, idx) => {
                  const config = subsystemConfig[event.subsystem]
                  return (
                    <motion.div
                      key={event.id}
                      custom={idx}
                      variants={itemVariants}
                      initial="hidden"
                      animate="visible"
                      layout
                      className="relative mb-4 pl-10 last:mb-0"
                    >
                      <div
                        className={cn(
                          "absolute left-0 top-0.5 flex h-[38px] w-[38px] items-center justify-center rounded-full border-2 bg-white",
                          config.color
                        )}
                      >
                        {config.icon}
                      </div>

                      <div className="rounded-xl border border-[#E8EDF3] bg-white p-3.5 transition-colors hover:bg-gray-50/60">
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0 flex-1">
                            <p className="text-[13px] font-semibold text-gray-900">{event.title}</p>
                            <p className="mt-0.5 text-[12px] leading-snug text-gray-500 line-clamp-2">
                              {event.description}
                            </p>
                          </div>
                          <span className="flex shrink-0 items-center gap-1 whitespace-nowrap text-[11px] text-gray-400">
                            <Clock size={11} />
                            {timeAgo(event.timestamp)}
                          </span>
                        </div>

                        <div className="mt-2 flex items-center gap-2">
                          <span
                            className={cn(
                              "rounded-md border px-2 py-0.5 text-[10px] font-medium",
                              config.color
                            )}
                          >
                            {config.label}
                          </span>
                          <span className="text-[10px] text-gray-400">via {event.source}</span>
                        </div>
                      </div>
                    </motion.div>
                  )
                })}
              </AnimatePresence>
            </div>
          )}
        </div>

        {hasMore && (
          <div className="border-t border-[#E8EDF3] px-5 py-3">
            <button
              onClick={() => setVisibleCount((prev) => prev + PAGE_SIZE)}
              className="flex w-full items-center justify-center gap-2 rounded-xl py-2 text-[13px] font-medium text-blue-600 transition-colors hover:bg-blue-50"
            >
              <Loader2 size={14} />
              Load More ({filteredEvents.length - visibleCount} remaining)
              <ChevronDown size={14} />
            </button>
          </div>
        )}
      </div>
    </div>
  )
}