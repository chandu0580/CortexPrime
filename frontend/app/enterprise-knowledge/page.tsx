"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import CortexShell from "@/components/layout/CortexShell"
import { stagger, variants } from "@/lib/motion-tokens"
import { useEnterpriseSearch, useEnterpriseEntityTypes, useEnterpriseEntities, useEnterpriseMissionGraph, useEnterpriseRecentMissions } from "@/hooks/queries/enterprise/useEnterpriseSearch"
import { SearchResult } from "@/services/enterprise/knowledge"
import { Search, Database, GitBranch, Clock, Shield, FileText, CheckCircle2, AlertTriangle, Activity, Loader2 } from "lucide-react"

const sourceIcons: Record<string, React.ElementType> = {
  neo4j: Database,
  connectors: GitBranch,
  replay: Clock,
  audit: Shield,
  memory: FileText,
}

const sourceColors: Record<string, string> = {
  neo4j: "text-purple-600 bg-purple-50 border-purple-200",
  connectors: "text-blue-600 bg-blue-50 border-blue-200",
  replay: "text-amber-600 bg-amber-50 border-amber-200",
  audit: "text-red-600 bg-red-50 border-red-200",
  memory: "text-green-600 bg-green-50 border-green-200",
}

function SourceBadge({ source }: { source: string }) {
  const Icon = sourceIcons[source] || Database
  const colors = sourceColors[source] || "text-gray-600 bg-gray-50 border-gray-200"
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[0.7rem] font-medium ${colors}`}>
      <Icon className="h-3 w-3" />
      {source}
    </span>
  )
}

function ResultsList({ results }: { results: SearchResult[] }) {
  if (results.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-[#6B7280]">
        <Search className="mb-3 h-10 w-10 opacity-30" />
        <p className="text-sm">No results found. Try a different search term.</p>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {results.map((r, i) => (
        <motion.div
          key={`${r.source}-${r.id}-${i}`}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.03 }}
          className="group cursor-pointer rounded-lg border border-[#E8EDF3] bg-white p-3.5 transition-all hover:border-[#38B88A]/30 hover:shadow-sm"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <SourceBadge source={r.source} />
                <span className="rounded bg-[#F0FDF4] px-1.5 py-0.5 text-[0.65rem] font-medium text-[#38B88A]">
                  {r.label}
                </span>
              </div>
              <p className="mt-1.5 text-sm font-semibold text-[#111827]">{r.title || "Untitled"}</p>
              <p className="mt-0.5 line-clamp-2 text-[0.78rem] text-[#6B7280]">
                {typeof r.description === "object" && r.description
                  ? JSON.stringify(r.description).slice(0, 200)
                  : String(r.description ?? "")}
              </p>
            </div>
            <div className="shrink-0 text-right">
              <span className="text-[0.65rem] font-medium text-[#9CA3AF]">
                {(r.score * 100).toFixed(0)}%
              </span>
            </div>
          </div>
          {r.id && (
            <p className="mt-1 truncate text-[0.65rem] text-[#9CA3AF]">ID: {r.id}</p>
          )}
        </motion.div>
      ))}
    </div>
  )
}

function EntityBrowser({ type }: { type: string }) {
  const { data: entities, isLoading } = useEnterpriseEntities(type)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8 text-[0.78rem] text-[#6B7280]">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        Loading entities...
      </div>
    )
  }

  if (!entities || entities.length === 0) {
    return <p className="py-6 text-center text-[0.78rem] text-[#9CA3AF]">No entities found</p>
  }

  return (
    <div className="max-h-80 space-y-1.5 overflow-y-auto">
      {entities.map((e, i) => {
        const ent = e as Record<string, unknown>
        return (
        <div key={i} className="rounded-md border border-[#E8EDF3] bg-white px-3 py-2 text-[0.78rem]">
          <p className="font-medium text-[#111827]">
            {String(ent.objective || ent.name || ent.description || ent.action_id || ent.execution_id || `Entity ${i + 1}`)}
          </p>
          {ent.status ? (
            <span className="mt-0.5 inline-block rounded bg-[#F0FDF4] px-1.5 py-0.5 text-[0.6rem] font-medium text-[#38B88A]">
              {String(ent.status)}
            </span>
          ) : null}
          {ent.started_at ? (
            <p className="mt-0.5 text-[0.65rem] text-[#9CA3AF]">{String(ent.started_at)}</p>
          ) : null}
        </div>
        )
      })}
    </div>
  )
}

function RecentMissionsPanel() {
  const { data: missions, isLoading } = useEnterpriseRecentMissions()

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8 text-[0.78rem] text-[#6B7280]">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        Loading missions...
      </div>
    )
  }

  if (!missions || missions.length === 0) {
    return <p className="py-6 text-center text-[0.78rem] text-[#9CA3AF]">No missions found</p>
  }

  return (
    <div className="space-y-2">
      {missions.slice(0, 10).map((m, i) => {
        const mission = m as Record<string, unknown>
        const status = (mission.status as string) || "unknown"
        const isCompleted = status === "completed"
        const isFailed = status === "failed"
        return (
          <div key={i} className="flex items-center gap-3 rounded-lg border border-[#E8EDF3] bg-white px-3.5 py-2.5">
            {isCompleted ? (
              <CheckCircle2 className="h-4 w-4 shrink-0 text-[#38B88A]" />
            ) : isFailed ? (
              <AlertTriangle className="h-4 w-4 shrink-0 text-red-500" />
            ) : (
              <Activity className="h-4 w-4 shrink-0 text-amber-500" />
            )}
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-[#111827]">
                {String(mission.objective || mission.template_name || `Mission ${i + 1}`)}
              </p>
              <p className="text-[0.7rem] text-[#6B7280]">
                {String(mission.template_name)} — {String(mission.started_at)}
              </p>
            </div>
            <span className={`shrink-0 rounded px-2 py-0.5 text-[0.65rem] font-medium ${
              isCompleted
                ? "bg-[#F0FDF4] text-[#38B88A]"
                : isFailed
                ? "bg-red-50 text-red-600"
                : "bg-amber-50 text-amber-600"
            }`}>
              {status}
            </span>
          </div>
        )
      })}
    </div>
  )
}

export default function EnterpriseKnowledgeCenter() {
  const [query, setQuery] = useState("")
  const [debouncedQuery, setDebouncedQuery] = useState("")
  const [sourceFilter, setSourceFilter] = useState<string>("")
  const [selectedType, setSelectedType] = useState("EnterpriseMission")

  const { data: searchResults, isLoading: isSearching } = useEnterpriseSearch(
    debouncedQuery,
    sourceFilter || undefined,
  )
  const { data: entityTypes } = useEnterpriseEntityTypes()

  const handleSearch = (value: string) => {
    setQuery(value)
    const timer = setTimeout(() => setDebouncedQuery(value), 400)
    return () => clearTimeout(timer)
  }

  return (
    <CortexShell title="Enterprise Knowledge Center" subtitle="Universal search, graph exploration, and mission lineage">
      <div className="relative z-10 mx-auto max-w-7xl space-y-6">
        {/* Search Section */}
        <motion.div initial="hidden" animate="visible" variants={stagger(0.04, 0.01)} className="space-y-4">
          <motion.div variants={variants.fadeUp} className="relative">
            <div className="relative flex items-center">
              <Search className="absolute left-4 h-4 w-4 text-[#9CA3AF]" />
              <input
                type="text"
                value={query}
                onChange={(e) => handleSearch(e.target.value)}
                placeholder="Search across missions, connectors, audit, memory, and graph entities..."
                className="w-full rounded-xl border border-[#E8EDF3] bg-white py-3.5 pl-11 pr-4 text-sm text-[#111827] placeholder-[#9CA3AF] outline-none transition-all focus:border-[#38B88A]/40 focus:shadow-[0_0_0_3px_rgba(56,184,138,0.08)]"
              />
            </div>

            {/* Source filter chips */}
            <div className="mt-3 flex flex-wrap gap-2">
              {["", "neo4j", "connectors", "replay", "audit", "memory"].map((src) => (
                <button
                  key={src}
                  onClick={() => setSourceFilter(sourceFilter === src ? "" : src)}
                  className={`rounded-full border px-3 py-1 text-[0.7rem] font-medium transition-all ${
                    sourceFilter === src
                      ? "border-[#38B88A] bg-[#38B88A] text-white"
                      : "border-[#E8EDF3] bg-white text-[#6B7280] hover:border-[#38B88A]/30"
                  }`}
                >
                  {src || "All"}
                </button>
              ))}
            </div>
          </motion.div>

          {/* Search Results */}
          {debouncedQuery && (
            <motion.div variants={variants.fadeUp}>
              {isSearching ? (
                <div className="flex items-center justify-center py-12 text-sm text-[#6B7280]">
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Searching...
                </div>
              ) : (
                <ResultsList results={searchResults ?? []} />
              )}
            </motion.div>
          )}
        </motion.div>

        {/* Graph Explorer + Recent Missions */}
        <motion.div initial="hidden" animate="visible" variants={stagger(0.05, 0.03)} className="grid gap-5 lg:grid-cols-2">
          {/* Entity Browser */}
          <motion.div variants={variants.fadeUp} className="rounded-xl border border-[#E8EDF3] bg-white p-5">
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Database className="h-4 w-4 text-[#38B88A]" />
                <h2 className="text-sm font-bold text-[#111827]">Entity Browser</h2>
              </div>
            </div>

            <div className="mb-3 flex flex-wrap gap-1.5">
              {(entityTypes ?? []).map((t) => (
                <button
                  key={t.label}
                  onClick={() => setSelectedType(t.label)}
                  className={`rounded-full px-2.5 py-1 text-[0.65rem] font-medium transition-all ${
                    selectedType === t.label
                      ? "bg-[#38B88A] text-white"
                      : "bg-[#F4F7FA] text-[#6B7280] hover:bg-[#E8EDF3]"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>

            <EntityBrowser type={selectedType} />
          </motion.div>

          {/* Recent Missions */}
          <motion.div variants={variants.fadeUp} className="rounded-xl border border-[#E8EDF3] bg-white p-5">
            <div className="mb-4 flex items-center gap-2">
              <Activity className="h-4 w-4 text-[#38B88A]" />
              <h2 className="text-sm font-bold text-[#111827]">Recent Missions</h2>
            </div>
            <RecentMissionsPanel />
          </motion.div>
        </motion.div>

        {/* Summary Stats */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="rounded-xl border border-[#E8EDF3] bg-white p-5"
        >
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-[#38B88A]" />
            <h2 className="text-sm font-bold text-[#111827]">Knowledge Graph Summary</h2>
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {[
              { label: "Entity Types", value: (entityTypes ?? []).length, icon: Database },
              { label: "Search Sources", value: 5, icon: Search },
              { label: "Recent Missions", value: (searchResults ?? []).filter(r => r.label === "EnterpriseMission").length, icon: Activity },
              { label: "Connected Services", value: "5", icon: GitBranch },
            ].map((stat, i) => {
              const Icon = stat.icon
              return (
                <div key={i} className="rounded-lg border border-[#E8EDF3] bg-[#FAFBFC] p-3.5">
                  <div className="flex items-center gap-2">
                    <Icon className="h-3.5 w-3.5 text-[#38B88A]" />
                    <span className="text-[0.7rem] font-medium text-[#6B7280]">{stat.label}</span>
                  </div>
                  <p className="mt-1 text-xl font-bold text-[#111827]">{stat.value}</p>
                </div>
              )
            })}
          </div>
        </motion.div>
      </div>
    </CortexShell>
  )
}
