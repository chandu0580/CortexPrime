"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import CortexShell from "@/components/layout/CortexShell"
import { stagger, variants } from "@/lib/motion-tokens"
import {
  useCodeRepositories,
  useScanRepository,
  useCodeGraph,
  useCodeFunctions,
  useCodeClasses,
  useCodeDependencies,
  useAnalyzeImpact,
} from "@/hooks/queries/enterprise/useEnterpriseCodeIntelligence"
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Box,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Cpu,
  Database,
  FileCode,
  FileSearch,
  FolderOpen,
  Globe,
  Loader2,
  Network,
  Search,
  Shield,
  Target,
  Terminal,
  TrendingUp,
  XCircle,
} from "lucide-react"
import type { ImpactResult, RepositoryScan } from "@/types/code-intelligence"

const RISK_COLORS: Record<string, string> = {
  low: "text-[#38B88A] bg-[#F0FDF4]",
  medium: "text-amber-500 bg-amber-50",
  high: "text-orange-500 bg-orange-50",
  critical: "text-red-500 bg-red-50",
}

const LANG_COLORS: Record<string, string> = {
  python: "bg-blue-100 text-blue-600",
  typescript: "bg-indigo-100 text-indigo-600",
  javascript: "bg-yellow-100 text-yellow-600",
  java: "bg-red-100 text-red-600",
  go: "bg-cyan-100 text-cyan-600",
  rust: "bg-orange-100 text-orange-600",
  dotnet: "bg-purple-100 text-purple-600",
  shell: "bg-gray-100 text-gray-600",
  docker: "bg-sky-100 text-sky-600",
}

export default function CodeIntelligenceCenter() {
  const [activeTab, setActiveTab] = useState("explorer")
  const [scanPath, setScanPath] = useState("")
  const [impactFile, setImpactFile] = useState("")
  const [impactResult, setImpactResult] = useState<ImpactResult | null>(null)
  const [expandedEntities, setExpandedEntities] = useState<Set<string>>(new Set())
  const [selectedNode, setSelectedNode] = useState("")

  const { data: repos } = useCodeRepositories()
  const scanMutation = useScanRepository()
  const { data: graph } = useCodeGraph()
  const { data: functions } = useCodeFunctions()
  const { data: classes } = useCodeClasses()
  const { data: deps } = useCodeDependencies(selectedNode || undefined)
  const impactMutation = useAnalyzeImpact()
  const [scanResult, setScanResult] = useState<RepositoryScan | null>(null)
  const [error, setError] = useState("")

  const handleScan = async () => {
    if (!scanPath) return
    setError("")
    try {
      const result = await scanMutation.mutateAsync(scanPath)
      setScanResult(result)
    } catch (err: any) {
      setError(err?.response?.data?.detail || String(err))
    }
  }

  const handleImpact = async () => {
    if (!impactFile) return
    try {
      const result = await impactMutation.mutateAsync({ changedFile: impactFile })
      setImpactResult(result)
    } catch (err) { console.error(err) }
  }

  const toggleExpand = (id: string) => {
    const next = new Set(expandedEntities)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setExpandedEntities(next)
  }

  const tabs = [
    { id: "explorer", label: "Explorer", icon: FolderOpen },
    { id: "graph", label: "Graph", icon: Network },
    { id: "functions", label: "Functions", icon: FileCode },
    { id: "classes", label: "Classes", icon: Box },
    { id: "impact", label: "Impact", icon: Target },
  ]

  return (
    <CortexShell title="Code Intelligence" subtitle="Source code understanding, dependency analysis, and impact prediction">
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
        </div>

        {/* ── Explorer ── */}
        {activeTab === "explorer" && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
            <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
              <h3 className="mb-3 text-sm font-bold text-[#111827]">Scan Repository</h3>
              <div className="flex gap-2">
                <input value={scanPath} onChange={e => setScanPath(e.target.value)} placeholder="Absolute path to repository"
                  className="flex-1 rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] outline-none" />
                <button onClick={handleScan} disabled={!scanPath || scanMutation.isPending}
                  className="flex items-center gap-1.5 rounded-lg bg-[#38B88A] px-4 py-2 text-[0.72rem] font-bold text-white disabled:opacity-50">
                  {scanMutation.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Search className="h-3.5 w-3.5" />}
                  Scan
                </button>
              </div>
            </div>

            {error && (
              <div className="flex items-center gap-2 rounded-xl border border-red-300 bg-red-50 p-4">
                <XCircle className="h-4 w-4 text-red-500" />
                <span className="text-[0.72rem] text-red-600">{error}</span>
              </div>
            )}

            {scanResult && (
              <div className="space-y-4">
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  {[
                    { icon: FileCode, label: "Files", value: scanResult.total_files, color: "bg-blue-500" },
                    { icon: Cpu, label: "Languages", value: Object.keys(scanResult.languages).length, color: "bg-[#38B88A]" },
                    { icon: Box, label: "Entities", value: scanResult.entity_count, color: "bg-purple-500" },
                    { icon: FolderOpen, label: "Modules", value: scanResult.modules.length, color: "bg-amber-500" },
                  ].map((stat, i) => (
                    <div key={i} className="rounded-xl border border-[#E8EDF3] bg-white p-4">
                      <div className="flex items-center gap-3">
                        <div className={`rounded-lg p-2.5 ${stat.color}`}><stat.icon className="h-4 w-4 text-white" /></div>
                        <div>
                          <p className="text-[0.7rem] font-medium text-[#6B7280]">{stat.label}</p>
                          <p className="text-xl font-bold text-[#111827]">{stat.value}</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Languages */}
                <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                  <h3 className="mb-3 text-sm font-bold text-[#111827]">Languages</h3>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(scanResult.languages).map(([lang, count]) => (
                      <span key={lang} className={`rounded px-2.5 py-1 text-[0.6rem] font-medium ${LANG_COLORS[lang] || "bg-gray-100 text-gray-600"}`}>
                        {lang} ({count})
                      </span>
                    ))}
                  </div>
                </div>

                {/* Entities */}
                <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                  <h3 className="mb-3 text-sm font-bold text-[#111827]">Code Entities ({scanResult.entity_count})</h3>
                  <div className="space-y-1">
                    {scanResult.entities.slice(0, 100).map((e, i) => (
                      <div key={e.id || i}>
                        <button onClick={() => toggleExpand(e.id)}
                          className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-[0.6rem] hover:bg-[#FAFBFC]">
                          {expandedEntities.has(e.id) ? <ChevronDown className="h-3 w-3 text-[#9CA3AF]" /> : <ChevronRight className="h-3 w-3 text-[#9CA3AF]" />}
                          <span className={`rounded px-1.5 py-0.5 text-[0.45rem] font-medium ${
                            e.entity_type === "function" || e.entity_type === "async_function" ? "bg-blue-50 text-blue-500" :
                            e.entity_type === "class" ? "bg-purple-50 text-purple-500" :
                            e.entity_type === "route" ? "bg-green-50 text-green-500" :
                            e.entity_type === "service" ? "bg-amber-50 text-amber-500" :
                            e.entity_type === "model" ? "bg-red-50 text-red-500" :
                            "bg-gray-50 text-gray-500"
                          }`}>{e.entity_type}</span>
                          <span className="font-medium text-[#111827]">{e.name}</span>
                          <span className="text-[#9CA3AF]">{e.file_path}:{e.line_start}</span>
                        </button>
                        {expandedEntities.has(e.id) && (
                          <div className="ml-8 rounded-lg bg-[#FAFBFC] p-2 text-[0.55rem] text-[#6B7280]">
                            {e.docstring && <p className="mb-1 italic">{e.docstring}</p>}
                            {e.metadata && Object.keys(e.metadata).length > 0 && (
                              <pre className="font-mono">{JSON.stringify(e.metadata, null, 2).slice(0, 300)}</pre>
                            )}
                            {e.relationships.length > 0 && (
                              <div className="mt-1">
                                <span className="text-[0.5rem] text-[#9CA3AF]">Relationships ({e.relationships.length}):</span>
                                {e.relationships.slice(0, 5).map((r, ri) => (
                                  <span key={ri} className="ml-1 rounded bg-[#E8EDF3] px-1 py-0.5">{r.type}: {r.target_name}</span>
                                ))}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>

                {/* Build Systems */}
                {scanResult.build_systems.length > 0 && (
                  <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                    <h3 className="mb-3 text-sm font-bold text-[#111827]">Build Systems</h3>
                    <div className="flex flex-wrap gap-2">
                      {scanResult.build_systems.map(bs => (
                        <span key={bs} className="rounded bg-[#F4F7FA] px-2.5 py-1 text-[0.6rem] font-medium text-[#6B7280]">{bs}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {!scanResult && !error && (
              <div className="flex flex-col items-center rounded-xl border border-[#E8EDF3] bg-white py-16 text-[#9CA3AF]">
                <FileSearch className="mb-3 h-10 w-10 opacity-30" />
                <p className="text-sm">Enter a repository path and click Scan.</p>
              </div>
            )}
          </motion.div>
        )}

        {/* ── Graph ── */}
        {activeTab === "graph" && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                <h3 className="mb-3 text-sm font-bold text-[#111827]">Dependency Graph</h3>
                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-lg bg-[#FAFBFC] p-3 text-center">
                    <p className="text-2xl font-bold text-[#111827]">{graph?.node_count ?? 0}</p>
                    <p className="text-[0.6rem] text-[#6B7280]">Nodes</p>
                  </div>
                  <div className="rounded-lg bg-[#FAFBFC] p-3 text-center">
                    <p className="text-2xl font-bold text-[#111827]">{graph?.edge_count ?? 0}</p>
                    <p className="text-[0.6rem] text-[#6B7280]">Edges</p>
                  </div>
                </div>
              </div>

              <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                <h3 className="mb-3 text-sm font-bold text-[#111827]">Node Explorer</h3>
                <input value={selectedNode} onChange={e => setSelectedNode(e.target.value)} placeholder="Node ID to inspect"
                  className="mb-2 w-full rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.72rem] outline-none font-mono" />
                {deps && (
                  <div className="space-y-1 text-[0.55rem]">
                    <p className="text-[#6B7280]">Connected edges: {deps.edges?.length ?? 0}</p>
                    {(deps.edges ?? []).slice(0, 10).map((e, i) => (
                      <div key={i} className="flex items-center gap-1 text-[#9CA3AF]">
                        <Network className="h-2.5 w-2.5" />
                        <span className="font-mono">{e.type}</span>
                        <span>{e.source} → {e.target}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Graph nodes list */}
            {graph && graph.nodes.length > 0 && (
              <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                <h3 className="mb-3 text-sm font-bold text-[#111827]">All Nodes</h3>
                <div className="max-h-80 space-y-1 overflow-auto">
                  {graph.nodes.map((n, i) => (
                    <div key={n.id || i} className="flex items-center gap-2 rounded-lg bg-[#FAFBFC] px-2.5 py-1.5 text-[0.6rem]">
                      <span className={`rounded px-1.5 py-0.5 text-[0.45rem] font-medium ${
                        n.type === "Function" ? "bg-blue-50 text-blue-500" :
                        n.type === "Class" ? "bg-purple-50 text-purple-500" :
                        n.type === "Route" ? "bg-green-50 text-green-500" :
                        "bg-gray-50 text-gray-500"
                      }`}>{n.type}</span>
                      <span className="font-medium text-[#111827]">{n.name}</span>
                      <span className="text-[#9CA3AF]">{n.file_path}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        )}

        {/* ── Functions ── */}
        {activeTab === "functions" && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-3">
            {functions?.functions && functions.functions.length > 0 ? (
              functions.functions.map((f: any, i: number) => (
                <div key={i} className="rounded-xl border border-[#E8EDF3] bg-white p-4">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2">
                      <FileCode className="h-3.5 w-3.5 text-blue-500" />
                      <span className="text-[0.72rem] font-bold text-[#111827]">{f.name}</span>
                      <span className="rounded bg-blue-50 px-1.5 py-0.5 text-[0.45rem] text-blue-500">{(f as any).properties?.file_path || f.file_path}</span>
                    </div>
                    <span className="text-[0.5rem] text-[#9CA3AF]">L{(f as any).properties?.line_start || f.line_start}</span>
                  </div>
                </div>
              ))
            ) : (
              <div className="flex flex-col items-center rounded-xl border border-[#E8EDF3] bg-white py-16 text-[#9CA3AF]">
                <FileCode className="mb-3 h-10 w-10 opacity-30" />
                <p className="text-sm">No functions parsed yet. Scan a repository first.</p>
              </div>
            )}
          </motion.div>
        )}

        {/* ── Classes ── */}
        {activeTab === "classes" && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-3">
            {classes?.classes && classes.classes.length > 0 ? (
              classes.classes.map((c: any, i: number) => (
                <div key={i} className="rounded-xl border border-[#E8EDF3] bg-white p-4">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2">
                      <Box className="h-3.5 w-3.5 text-purple-500" />
                      <span className="text-[0.72rem] font-bold text-[#111827]">{c.name}</span>
                      <span className="rounded bg-purple-50 px-1.5 py-0.5 text-[0.45rem] text-purple-500">{(c as any).properties?.file_path || c.file_path}</span>
                    </div>
                    <span className="text-[0.5rem] text-[#9CA3AF]">
                      {(c as any).properties?.metadata?.bases ? `extends ${(c as any).properties.metadata.bases.join(", ")}` : ""}
                    </span>
                  </div>
                </div>
              ))
            ) : (
              <div className="flex flex-col items-center rounded-xl border border-[#E8EDF3] bg-white py-16 text-[#9CA3AF]">
                <Box className="mb-3 h-10 w-10 opacity-30" />
                <p className="text-sm">No classes parsed yet. Scan a repository first.</p>
              </div>
            )}
          </motion.div>
        )}

        {/* ── Impact ── */}
        {activeTab === "impact" && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
            <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
              <h3 className="mb-3 text-sm font-bold text-[#111827]">Impact Analysis</h3>
              <p className="mb-3 text-[0.6rem] text-[#6B7280]">Analyze what would break if a file is changed.</p>
              <div className="flex gap-2">
                <input value={impactFile} onChange={e => setImpactFile(e.target.value)} placeholder="File path relative to repo root"
                  className="flex-1 rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] outline-none font-mono" />
                <button onClick={handleImpact} disabled={!impactFile || impactMutation.isPending}
                  className="flex items-center gap-1.5 rounded-lg bg-[#38B88A] px-4 py-2 text-[0.72rem] font-bold text-white disabled:opacity-50">
                  {impactMutation.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Target className="h-3.5 w-3.5" />}
                  Analyze
                </button>
              </div>
            </div>

            {impactResult && (
              <div className="space-y-4">
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  {[
                    { icon: Shield, label: "Risk Score", value: `${impactResult.risk_score}/100`, color: impactResult.risk_level === "critical" ? "bg-red-500" : impactResult.risk_level === "high" ? "bg-orange-500" : impactResult.risk_level === "medium" ? "bg-amber-500" : "bg-[#38B88A]" },
                    { icon: FileCode, label: "Affected Files", value: impactResult.total_dependents, color: "bg-blue-500" },
                    { icon: Globe, label: "Affected APIs", value: impactResult.affected_apis.length, color: "bg-purple-500" },
                    { icon: Terminal, label: "Affected Tests", value: impactResult.affected_tests.length, color: "bg-amber-500" },
                  ].map((stat, i) => {
                    const Icon = stat.icon
                    return (
                      <div key={i} className="rounded-xl border border-[#E8EDF3] bg-white p-4">
                        <div className="flex items-center gap-3">
                          <div className={`rounded-lg p-2.5 ${stat.color}`}><Icon className="h-4 w-4 text-white" /></div>
                          <div>
                            <p className="text-[0.7rem] font-medium text-[#6B7280]">{stat.label}</p>
                            <p className="text-xl font-bold text-[#111827]">{stat.value}</p>
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>

                <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                  <div className="mb-3 flex items-center gap-2">
                    <h3 className="text-sm font-bold text-[#111827]">Risk Level</h3>
                    <span className={`rounded px-2 py-0.5 text-[0.55rem] font-medium ${RISK_COLORS[impactResult.risk_level] || "text-gray-500 bg-gray-100"}`}>
                      {impactResult.risk_level.toUpperCase()}
                    </span>
                  </div>
                  <p className="text-[0.65rem] text-[#6B7280]">Changed file: <span className="font-mono text-[#111827]">{impactResult.changed_file}</span></p>
                </div>

                {[
                  { label: "Affected Files", items: impactResult.all_affected_files, icon: FileCode },
                  { label: "Affected APIs", items: impactResult.affected_apis, icon: Globe },
                  { label: "Affected Services", items: impactResult.affected_services, icon: Cpu },
                  { label: "Affected Models", items: impactResult.affected_models, icon: Database },
                  { label: "Affected Tests", items: impactResult.affected_tests, icon: Terminal },
                  { label: "Affected Frontend", items: impactResult.affected_frontend_components, icon: Activity },
                ].map(section => section.items.length > 0 && (
                  <div key={section.label} className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                    <h3 className="mb-2 flex items-center gap-2 text-sm font-bold text-[#111827]">
                      <section.icon className="h-3.5 w-3.5 text-[#6B7280]" />
                      {section.label} ({section.items.length})
                    </h3>
                    <div className="space-y-1">
                      {section.items.slice(0, 20).map((item, i) => (
                        <div key={i} className="rounded-lg bg-[#FAFBFC] px-2.5 py-1.5 text-[0.6rem] text-[#6B7280] font-mono">
                          {item}
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </motion.div>
        )}
      </div>
    </CortexShell>
  )
}
