"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Building2, Plus, RefreshCw, Trash2, Play, Layers, Database,
  Code2, Zap, Cpu, GitFork, FileText, ListTodo, Activity,
  CheckCircle, Clock, Loader2, ArrowRight,
} from "lucide-react"
import { useArchitectureProjects, useArchitectureDashboard, useAnalyzeArchitecture, useDeleteArchitectureProject } from "@/hooks/queries/enterprise/useEnterpriseArchitecture"
import type { ArchitectureProject } from "@/types/architecture"

type Tab = "dashboard" | "requirements" | "domains" | "services" | "database" | "apis" | "events" | "technology" | "plan"

export default function EnterpriseArchitecturePage() {
  const [showInput, setShowInput] = useState(false)
  const [inputText, setInputText] = useState("")
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [tab, setTab] = useState<Tab>("dashboard")
  const [filter, setFilter] = useState("")

  const { data: projects = [], refetch } = useArchitectureProjects(filter === "all" ? "" : filter)
  const { data: dashboard } = useArchitectureDashboard()
  const analyzeArch = useAnalyzeArchitecture()
  const deleteArch = useDeleteArchitectureProject()

  const selectedProject = projects.find((p) => p.project_id === selectedId)

  const handleAnalyze = async () => {
    const trimmed = inputText.trim()
    if (!trimmed) return
    try {
      const result = await analyzeArch.mutateAsync({ inputText: trimmed })
      setSelectedId(result.project.project_id)
      setInputText("")
      setShowInput(false)
      refetch()
    } catch { /* ignore */ }
  }

  const handleDelete = async (id: string) => {
    try {
      await deleteArch.mutateAsync(id)
      if (selectedId === id) setSelectedId(null)
      refetch()
    } catch { /* ignore */ }
  }

  return (
    <div className="min-h-screen bg-black text-gray-100 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Building2 className="w-7 h-7 text-blue-400" />
            <h1 className="text-2xl font-bold">AI CTO — Architecture Intelligence</h1>
          </div>
          <div className="flex gap-2">
            <button onClick={() => refetch()} className="p-2 rounded-lg bg-gray-800 hover:bg-gray-700 border border-gray-700">
              <RefreshCw className="w-4 h-4" />
            </button>
            <button onClick={() => setShowInput(!showInput)} className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium">
              <Plus className="w-4 h-4" /> New Analysis
            </button>
          </div>
        </div>

        {/* Dashboard Stats */}
        {dashboard && (
          <div className="grid grid-cols-5 gap-3">
            {[
              { label: "Projects", value: dashboard.total_projects, color: "text-blue-400" },
              { label: "Analyzed", value: dashboard.analyzed, color: "text-green-400" },
              { label: "Pending", value: dashboard.pending, color: "text-yellow-400" },
              { label: "Industries", value: Object.keys(dashboard.by_industry).length, color: "text-purple-400" },
              { label: "By Industry", value: Object.entries(dashboard.by_industry).map(([k, v]) => `${k}:${v}`).join(" "), color: "text-gray-400", small: true },
            ].map((s) => (
              <div key={s.label} className="bg-gray-900 border border-gray-700 rounded-lg p-3 text-center">
                <div className={`text-2xl font-bold ${s.color} ${s.small ? "text-xs" : ""}`}>{s.value}</div>
                <div className="text-xs text-gray-500">{s.label}</div>
              </div>
            ))}
          </div>
        )}

        {/* Input Form */}
        <AnimatePresence>
          {showInput && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="bg-gray-900 border border-gray-700 rounded-lg p-4 space-y-3 overflow-hidden"
            >
              <h2 className="text-sm font-semibold">Enter Business Requirements</h2>
              <textarea
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder='e.g. "Build an Enterprise Hospital Management System"'
                rows={4}
                className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm font-mono"
              />
              <div className="flex gap-2">
                <button onClick={handleAnalyze} disabled={!inputText.trim()} className="flex items-center gap-2 px-4 py-2 rounded bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-sm font-medium">
                  <Play className="w-4 h-4" /> Analyze
                </button>
                <button onClick={() => setShowInput(false)} className="px-4 py-2 rounded bg-gray-700 hover:bg-gray-600 text-sm">
                  Cancel
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Filter Tabs */}
        <div className="flex gap-2 border-b border-gray-800 pb-2">
          {(["all", "analyzed", "created"] as const).map((f) => (
            <button key={f} onClick={() => setFilter(f === "all" ? "" : f)}
              className={`px-3 py-1 rounded text-sm font-medium ${filter === (f === "all" ? "" : f) ? "bg-blue-600 text-white" : "text-gray-400 hover:text-white"}`}>
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>

        {/* Main Content */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Project List */}
          <div className="lg:col-span-1 space-y-2">
            <h2 className="text-sm font-semibold text-gray-400 mb-2">Projects</h2>
            {projects.length === 0 && (
              <div className="text-center text-gray-600 py-8">
                <Building2 className="w-8 h-8 mx-auto mb-2 opacity-40" />
                <p className="text-sm">No projects yet</p>
              </div>
            )}
            <AnimatePresence>
              {projects.map((p) => (
                <motion.div
                  key={p.project_id}
                  layout
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  onClick={() => { setSelectedId(p.project_id); setTab("dashboard") }}
                  className={`cursor-pointer bg-gray-900 border rounded-lg p-3 space-y-1 ${
                    selectedId === p.project_id ? "border-blue-500 ring-1 ring-blue-500" : "border-gray-700 hover:border-gray-600"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium truncate">{p.name}</span>
                    {p.status === "analyzed" ? (
                      <CheckCircle className="w-3.5 h-3.5 text-green-400 flex-shrink-0" />
                    ) : (
                      <Clock className="w-3.5 h-3.5 text-yellow-400 flex-shrink-0" />
                    )}
                  </div>
                  <div className="text-xs text-gray-500">
                    {p.industry || "Unknown"} · {new Date(p.created_at).toLocaleDateString()}
                  </div>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleDelete(p.project_id); }}
                    className="text-xs text-red-400 hover:text-red-300"
                  >
                    Delete
                  </button>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>

          {/* Detail Panel */}
          <div className="lg:col-span-2">
            {!selectedProject ? (
              <div className="bg-gray-900 border border-gray-700 rounded-lg p-12 text-center">
                <Building2 className="w-16 h-16 mx-auto mb-4 opacity-20 text-blue-400" />
                <h2 className="text-xl font-semibold mb-2">Architecture Intelligence Center</h2>
                <p className="text-gray-500 text-sm max-w-md mx-auto">
                  Select a project or create a new analysis to transform business requirements into complete enterprise architecture blueprints, engineering plans, and executable missions.
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {/* Project Header */}
                <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-lg font-bold">{selectedProject.name}</h2>
                      <p className="text-sm text-gray-500">{selectedProject.description || selectedProject.input_text?.slice(0, 100)}</p>
                    </div>
                    <span className="text-xs text-gray-500 font-mono">{selectedProject.project_id.slice(0, 16)}</span>
                  </div>
                  <div className="flex gap-2 mt-2">
                    <span className="px-2 py-0.5 rounded text-xs bg-blue-900/40 text-blue-300">{selectedProject.industry || "Unknown"}</span>
                    <span className={`px-2 py-0.5 rounded text-xs ${selectedProject.status === "analyzed" ? "bg-green-900/40 text-green-300" : "bg-yellow-900/40 text-yellow-300"}`}>
                      {selectedProject.status}
                    </span>
                  </div>
                </div>

                {/* View Tabs */}
                <div className="flex flex-wrap gap-1.5">
                  {([
                    { id: "dashboard" as Tab, label: "Overview", icon: Activity },
                    { id: "requirements" as Tab, label: "Requirements", icon: FileText },
                    { id: "domains" as Tab, label: "Domain Model", icon: Layers },
                    { id: "services" as Tab, label: "Architecture", icon: Cpu },
                    { id: "database" as Tab, label: "Database", icon: Database },
                    { id: "apis" as Tab, label: "APIs", icon: Code2 },
                    { id: "events" as Tab, label: "Events", icon: GitFork },
                    { id: "technology" as Tab, label: "Tech Stack", icon: Zap },
                    { id: "plan" as Tab, label: "Engineering Plan", icon: ListTodo },
                  ]).map((t) => (
                    <button key={t.id} onClick={() => setTab(t.id)}
                      className={`flex items-center gap-1 px-3 py-1.5 rounded text-xs font-medium ${
                        tab === t.id ? "bg-blue-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white"
                      }`}>
                      <t.icon className="w-3.5 h-3.5" /> {t.label}
                    </button>
                  ))}
                </div>

                {/* Tab Content */}
                <div className="bg-gray-900 border border-gray-700 rounded-lg p-4 min-h-[300px]">
                  <TabContent project={selectedProject} tab={tab} />
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function TabContent({ project, tab }: { project: ArchitectureProject; tab: Tab }) {
  const reqs = project.requirements || {}
  const domain = project.domain || {}
  const arch = project.architecture || {}
  const tech = project.technology || {}
  const db = project.database || {}
  const apis = project.apis || {}
  const evts = project.events || {}
  const plan = project.plan || {}

  switch (tab) {
    case "dashboard":
      return <OverviewTab project={project} />
    case "requirements":
      return <RequirementsTab reqs={reqs} />
    case "domains":
      return <DomainTab domain={domain} />
    case "services":
      return <ServicesTab arch={arch} />
    case "database":
      return <DatabaseTab db={db} />
    case "apis":
      return <ApiTab apis={apis} />
    case "events":
      return <EventsTab evts={evts} />
    case "technology":
      return <TechTab tech={tech} />
    case "plan":
      return <PlanTab plan={plan} />
    default:
      return null
  }
}

function OverviewTab({ project }: { project: ArchitectureProject }) {
  const sections = [
    { label: "Functional Requirements", count: (Array.isArray(project.requirements) ? project.requirements : (project.requirements as Record<string, unknown>)?.functional_requirements as unknown[])?.length ?? 0 },
    { label: "Domain Entities", count: ((project.domain as Record<string, unknown>)?.entities as unknown[])?.length ?? 0 },
    { label: "Microservices", count: ((project.architecture as Record<string, unknown>)?.services as unknown[])?.length ?? 0 },
    { label: "API Endpoints", count: Number((project.apis as Record<string, unknown>)?.total_endpoints ?? 0) },
    { label: "Events", count: Number((project.events as Record<string, unknown>)?.total_events ?? 0) },
    { label: "Epics", count: Number((project.plan as Record<string, unknown>)?.total_epics ?? 0) },
  ]
  return (
    <div className="space-y-4">
      <h3 className="font-semibold">Architecture Overview</h3>
      <div className="grid grid-cols-3 gap-3">
        {sections.map((s) => (
          <div key={s.label} className="bg-gray-800 rounded p-3 text-center">
            <div className="text-2xl font-bold text-blue-400">{s.count}</div>
            <div className="text-xs text-gray-500">{s.label}</div>
          </div>
        ))}
      </div>
      {project.analyzed_at && (
        <p className="text-xs text-gray-600">Analyzed: {new Date(project.analyzed_at).toLocaleString()}</p>
      )}
    </div>
  )
}

function RequirementsTab({ reqs }: { reqs: Record<string, unknown> }) {
  const funcs = (reqs.functional_requirements as string[]) ?? []
  const nfs = (reqs.non_functional_requirements as string[]) ?? []
  const actors = (reqs.actors as string[]) ?? []
  return (
    <div className="space-y-4">
      <h3 className="font-semibold">Requirements Intelligence</h3>
      {reqs.industry ? <p className="text-sm text-gray-400">Industry: <span className="text-blue-300">{String(reqs.industry)}</span></p> : null}
      {funcs.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-green-400 mb-1">Functional Requirements ({funcs.length})</h4>
          <ul className="space-y-1">
            {funcs.map((r, i) => <li key={i} className="text-xs text-gray-300 flex items-start gap-1"><ArrowRight className="w-3 h-3 mt-0.5 text-green-500 flex-shrink-0" />{r}</li>)}
          </ul>
        </div>
      )}
      {nfs.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-yellow-400 mb-1">Non-Functional</h4>
          <ul className="space-y-1">
            {nfs.map((r, i) => <li key={i} className="text-xs text-gray-300 flex items-start gap-1"><ArrowRight className="w-3 h-3 mt-0.5 text-yellow-500 flex-shrink-0" />{r}</li>)}
          </ul>
        </div>
      )}
      {actors.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-purple-400 mb-1">Actors</h4>
          <div className="flex flex-wrap gap-1">
            {actors.map((a) => <span key={a} className="px-2 py-0.5 rounded text-xs bg-purple-900/40 text-purple-300">{a}</span>)}
          </div>
        </div>
      )}
    </div>
  )
}

function DomainTab({ domain }: { domain: Record<string, unknown> }) {
  const entities = (domain.entities as Record<string, unknown>[]) ?? []
  const contexts = (domain.bounded_contexts as Record<string, unknown>[]) ?? []
  const capabilities = (domain.capabilities as Record<string, unknown>[]) ?? []
  return (
    <div className="space-y-4">
      <h3 className="font-semibold">Domain Model</h3>
      {entities.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-blue-400 mb-1">Entities ({entities.length})</h4>
          <div className="grid grid-cols-2 gap-2">
            {entities.map((e) => (
              <div key={e.name as string} className="bg-gray-800 rounded p-2">
                <div className="text-sm font-medium">{e.name as string}</div>
                <div className="text-xs text-gray-500">{(e.attributes as string[])?.join(", ")}</div>
              </div>
            ))}
          </div>
        </div>
      )}
      {contexts.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-green-400 mb-1">Bounded Contexts</h4>
          <div className="flex flex-wrap gap-1">
            {contexts.map((c) => <span key={c.name as string} className="px-2 py-0.5 rounded text-xs bg-green-900/40 text-green-300">{c.name as string}</span>)}
          </div>
        </div>
      )}
      {capabilities.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-purple-400 mb-1">Business Capabilities</h4>
          <div className="space-y-1">
            {capabilities.map((c) => (
              <div key={c.name as string} className="flex items-center gap-2 text-xs">
                <span className="text-gray-300">{c.name as string}</span>
                <span className={`px-1 rounded text-xs ${c.priority === "high" ? "bg-red-900/40 text-red-300" : c.priority === "medium" ? "bg-yellow-900/40 text-yellow-300" : "bg-green-900/40 text-green-300"}`}>
                  {c.priority as string}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function ServicesTab({ arch: a }: { arch: Record<string, unknown> }) {
  const services = (a.services as Record<string, unknown>[]) ?? []
  return (
    <div className="space-y-4">
      <h3 className="font-semibold">System Architecture — Microservices</h3>
      <p className="text-xs text-gray-500">Pattern: {a.pattern as string}</p>
      {services.map((s) => (
        <div key={s.service_id as string} className="bg-gray-800 rounded p-3 border border-gray-700">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-medium text-blue-300">{s.name as string}</h4>
            <span className="text-xs text-gray-500">{s.language as string} / {s.framework as string}</span>
          </div>
          <p className="text-xs text-gray-500 mt-1">{s.description as string}</p>
          <div className="flex flex-wrap gap-1 mt-2">
            {(s.responsibilities as string[])?.map((r) => (
              <span key={r} className="px-1.5 py-0.5 rounded text-xs bg-blue-900/30 text-blue-300">{r}</span>
            ))}
          </div>
          {s.database ? <p className="text-xs text-gray-600 mt-1">DB: {String(s.database)}</p> : null}
        </div>
      ))}
      {a.auth_flow ? (
        <div className="bg-gray-800 rounded p-3 border border-gray-700 mt-2">
          <h4 className="text-sm font-medium text-yellow-300">Auth Flow</h4>
          <p className="text-xs text-gray-400">{String((a.auth_flow as Record<string, unknown>).protocol)}</p>
        </div>
      ) : null}
    </div>
  )
}

function DatabaseTab({ db }: { db: Record<string, unknown> }) {
  const tables = (db.tables as Record<string, unknown>[]) ?? []
  const mig = db.migration_strategy as Record<string, unknown> ?? {}
  return (
    <div className="space-y-4">
      <h3 className="font-semibold">Database Design</h3>
      {tables.map((t) => (
        <div key={t.table_name as string} className="bg-gray-800 rounded p-3 border border-gray-700">
          <h4 className="text-sm font-medium text-green-300">{t.table_name as string}</h4>
          <div className="mt-1 space-y-0.5">
            {(t.columns as Record<string, unknown>[])?.slice(0, 5).map((c) => (
              <div key={c.name as string} className="flex items-center gap-2 text-xs">
                <span className="text-gray-300">{c.name as string}</span>
                <span className="text-gray-500">{c.type as string}</span>
                {c.nullable === false && <span className="text-red-400">NOT NULL</span>}
              </div>
            ))}
          </div>
          {(t.indexes as string[])?.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {(t.indexes as string[])?.slice(0, 3).map((ix) => <span key={ix} className="px-1 py-0.5 rounded text-xs bg-yellow-900/30 text-yellow-300">{ix}</span>)}
            </div>
          )}
        </div>
      ))}
      {mig.tool ? <p className="text-xs text-gray-500 mt-2">Migration: {String(mig.tool)} — {String(mig.approach)}</p> : null}
    </div>
  )
}

function ApiTab({ apis }: { apis: Record<string, unknown> }) {
  const apiList = (apis.apis as Record<string, unknown>[]) ?? []
  return (
    <div className="space-y-4">
      <h3 className="font-semibold">API Contracts</h3>
      <p className="text-xs text-gray-500">Total endpoints: {apiList.length} · Versioning: {(apis.versioning as Record<string, unknown>)?.strategy as string}</p>
      <div className="max-h-80 overflow-y-auto space-y-1">
        {apiList.slice(0, 20).map((api, i) => (
          <div key={i} className="flex items-center gap-2 text-xs bg-gray-800 rounded px-2 py-1">
            <span className={`font-mono font-bold w-14 ${
              api.method === "POST" ? "text-green-400" : api.method === "GET" ? "text-blue-400" : api.method === "PATCH" ? "text-yellow-400" : "text-red-400"
            }`}>{api.method as string}</span>
            <span className="text-gray-300 font-mono">{api.path as string}</span>
            <span className="text-gray-500 ml-auto">{api.summary as string}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function EventsTab({ evts }: { evts: Record<string, unknown> }) {
  const domainEvents = (evts.domain_events as Record<string, unknown>[]) ?? []
  return (
    <div className="space-y-4">
      <h3 className="font-semibold">Event Architecture</h3>
      <p className="text-xs text-gray-500">Total events: {evts.total_events as number} · Queue: {(evts.queue_recommendations as Record<string, unknown>)?.technology as string}</p>
      <div className="max-h-80 overflow-y-auto space-y-1">
        {domainEvents.slice(0, 15).map((e, i) => (
          <div key={i} className="flex items-center gap-2 text-xs bg-gray-800 rounded px-2 py-1">
            <GitFork className="w-3 h-3 text-purple-400 flex-shrink-0" />
            <span className="text-gray-300">{e.event as string}</span>
            <span className="text-gray-500 ml-auto">{e.type as string}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function TechTab({ tech }: { tech: Record<string, unknown> }) {
  const decisions = (tech.decisions as Record<string, unknown>[]) ?? []
  return (
    <div className="space-y-4">
      <h3 className="font-semibold">Technology Decisions</h3>
      {decisions.map((cat) => (
        <div key={cat.layer as string} className="bg-gray-800 rounded p-3 border border-gray-700">
          <h4 className="text-sm font-medium text-blue-300 mb-2">{cat.layer as string}</h4>
          {(cat.choices as Record<string, unknown>[])?.map((c, i) => (
            <div key={i} className="mb-2 last:mb-0">
              <div className="flex items-center gap-2">
                <span className="text-sm text-green-300">{c.technology as string}</span>
                <span className={`px-1 rounded text-xs ${c.risk === "low" ? "bg-green-900/40 text-green-300" : "bg-yellow-900/40 text-yellow-300"}`}>
                  {c.risk as string} risk
                </span>
              </div>
              <p className="text-xs text-gray-400">{c.reason as string}</p>
              <p className="text-xs text-gray-600 mt-0.5">Alternatives: {(c.alternatives as string[])?.join(", ")}</p>
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}

function PlanTab({ plan }: { plan: Record<string, unknown> }) {
  const epics = (plan.epics as Record<string, unknown>[]) ?? []
  const missions = (plan.missions as Record<string, unknown>[]) ?? []
  return (
    <div className="space-y-4">
      <h3 className="font-semibold">Engineering Plan</h3>
      <p className="text-xs text-gray-500">
        {plan.total_epics as number} Epics · {plan.total_features as number} Features · {plan.total_stories as number} Stories
      </p>
      {epics.slice(0, 5).map((epic) => (
        <div key={epic.epic_id as string} className="bg-gray-800 rounded p-3 border border-gray-700">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-medium text-purple-300">{epic.name as string}</h4>
            <span className={`px-1 rounded text-xs ${epic.priority === "high" ? "bg-red-900/40 text-red-300" : "bg-yellow-900/40 text-yellow-300"}`}>
              {epic.priority as string}
            </span>
          </div>
          {(epic.features as Record<string, unknown>[])?.map((f, i) => (
            <div key={i} className="mt-1 text-xs text-gray-400 flex items-center gap-1">
              <ArrowRight className="w-3 h-3 flex-shrink-0" />
              {f.name as string}
            </div>
          ))}
          <p className="text-xs text-gray-600 mt-1">Effort: {epic.estimated_effort as string} · Risk: {epic.risk_score as string}</p>
        </div>
      ))}
      {missions.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-green-400 mt-4 mb-1">Generated Missions ({missions.length})</h4>
          <div className="flex flex-wrap gap-1">
            {missions.map((m) => (
              <span key={m.mission_id as string} className="px-2 py-0.5 rounded text-xs bg-green-900/40 text-green-300">
                {m.objective as string}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
