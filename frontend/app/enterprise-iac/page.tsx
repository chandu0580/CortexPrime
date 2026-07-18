"use client"
import { useState } from "react"
import { motion } from "framer-motion"
import CortexShell from "@/components/layout/CortexShell"
import { stagger, variants } from "@/lib/motion-tokens"
import {
  useTerraformReady,
  useTerraformWorkspaces,
  useTerraformCurrentWorkspace,
  useTerraformState,
  useTerraformOutputs,
  useTerraformProviders,
  useTerraformGraph,
  useTerraformDrift,
  useTerraformPlans,
  useTerraformInit,
  useTerraformValidate,
  useTerraformPlan,
  useTerraformApply,
  useTerraformDestroy,
  useTerraformCorrelate,
} from "@/hooks/queries/enterprise/useEnterpriseInfrastructure"
import {
  Activity, CheckCircle, XCircle, Clock, Loader2, AlertTriangle, RefreshCw,
  Server, Box, Layers, Shield, ExternalLink, ArrowRight,
  TrendingUp, TrendingDown, Minus, PlayCircle, RotateCcw, Search,
  Globe, Database, Network, Cpu, HardDrive, Lock, FileText, GitBranch,
} from "lucide-react"

const tabs = ["Dashboard", "Workspaces", "State", "Outputs", "Providers", "Graph", "Drift", "Plans", "Correlation"]

function StatusBadge({ status }: { status?: string }) {
  const s = (status || "").toLowerCase()
  if (s === "available" || s === "ready" || s === "healthy" || s === "synced" || s === "success" || s === "created" || s === "active")
    return <span className="inline-flex items-center gap-1 text-xs font-medium text-green-600 dark:text-green-400"><CheckCircle size={12} />{status}</span>
  if (s === "error" || s === "failed" || s === "degraded" || s === "missing" || s === "deleted" || s === "destroyed")
    return <span className="inline-flex items-center gap-1 text-xs font-medium text-red-600 dark:text-red-400"><XCircle size={12} />{status}</span>
  if (s === "pending" || s === "progressing" || s === "running" || s === "planning" || s === "applying")
    return <span className="inline-flex items-center gap-1 text-xs font-medium text-yellow-600 dark:text-yellow-400"><Clock size={12} />{status}</span>
  return <span className="inline-flex items-center gap-1 text-xs font-medium text-gray-500 dark:text-gray-400"><Activity size={12} />{status || "unknown"}</span>
}

function KpiCard({ icon: Icon, label, value, color }: { icon: any; label: string; value: number | string; color: string }) {
  return (
    <motion.div variants={variants.fadeIn} className={`rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 ${color}`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">{label}</p>
          <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">{value}</p>
        </div>
        <div className={`p-3 rounded-lg ${color.replace('text-', 'bg-').replace('600', '100').replace('500', '100')} dark:bg-gray-700`}>
          <Icon size={24} className={color} />
        </div>
      </div>
    </motion.div>
  )
}

function ResourceCategoryBadge({ category }: { category: string }) {
  const colors: Record<string, string> = {
    network: "bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300",
    compute: "bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300",
    cluster: "bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300",
    storage: "bg-cyan-100 dark:bg-cyan-900/30 text-cyan-700 dark:text-cyan-300",
    database: "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300",
    security: "bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300",
    loadbalancer: "bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300",
    dns: "bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-300",
    secret: "bg-pink-100 dark:bg-pink-900/30 text-pink-700 dark:text-pink-300",
    module: "bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300",
    provider: "bg-teal-100 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300",
  }
  return <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[category] || 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300'}`}>{category}</span>
}

const resourceTypeIcons: Record<string, any> = {
  network: Network, compute: Cpu, cluster: Layers, storage: HardDrive,
  database: Database, security: Lock, loadbalancer: Globe, dns: Globe,
  secret: Lock, module: Box, provider: Box,
}

export default function EnterpriseIacCenter() {
  const [activeTab, setActiveTab] = useState("Dashboard")
  const [workspace, setWorkspace] = useState("default")
  const [planResult, setPlanResult] = useState<any>(null)
  const [applyResult, setApplyResult] = useState<any>(null)

  const { data: ready } = useTerraformReady()
  const { data: workspaces, isLoading: wsLoading } = useTerraformWorkspaces()
  const { data: currentWs } = useTerraformCurrentWorkspace()
  const { data: stateData } = useTerraformState()
  const { data: outputs } = useTerraformOutputs()
  const { data: providers } = useTerraformProviders()
  const { data: graph } = useTerraformGraph()
  const { data: drift } = useTerraformDrift()
  const { data: plans } = useTerraformPlans()

  const initMut = useTerraformInit()
  const validateMut = useTerraformValidate()
  const planMut = useTerraformPlan()
  const applyMut = useTerraformApply()
  const destroyMut = useTerraformDestroy()
  const correlateMut = useTerraformCorrelate()

  const resources = stateData?.resources || []
  const resourceCount = stateData?.resource_count || resources.length
  const providerList = providers?.providers || []
  const driftList = drift?.drifts || []
  const planList = plans?.plans || []

  const categories = [...new Set(resources.map((r: any) => r.category || "other"))]
  const categoryCounts: Record<string, number> = {}
  resources.forEach((r: any) => {
    const cat = r.category || "other"
    categoryCounts[cat] = (categoryCounts[cat] || 0) + 1
  })

  return (
    <CortexShell>
      <motion.div variants={stagger()} initial="hidden" animate="visible" className="p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Enterprise IaC Center</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              Terraform — Infrastructure as Code management, drift detection, and progressive delivery
              {ready?.version && <span className="ml-2 inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400">v{ready.version}</span>}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500 dark:text-gray-400">Workspace:</span>
            <select value={workspace} onChange={e => setWorkspace(e.target.value)}
              className="text-sm border border-gray-300 dark:border-gray-600 rounded-lg px-2 py-1.5 bg-white dark:bg-gray-800 text-gray-900 dark:text-white">
              {(workspaces?.workspaces || [workspace]).map((w: string) => <option key={w} value={w}>{w}</option>)}
            </select>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 border-b border-gray-200 dark:border-gray-700 overflow-x-auto">
          {tabs.map(t => (
            <button key={t} onClick={() => setActiveTab(t)}
              className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px whitespace-nowrap ${activeTab === t ? 'border-blue-600 text-blue-600 dark:text-blue-400 dark:border-blue-400' : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'}`}>
              {t}
            </button>
          ))}
        </div>

        {activeTab === "Dashboard" && (
          <motion.div variants={stagger()} initial="hidden" animate="visible" className="space-y-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <KpiCard icon={Box} label="Resources" value={resourceCount} color="text-blue-600" />
              <KpiCard icon={Layers} label="Providers" value={providerList.length} color="text-purple-600" />
              <KpiCard icon={Server} label="Workspaces" value={workspaces?.total || 0} color="text-indigo-600" />
              <KpiCard icon={AlertTriangle} label="Drifts" value={driftList.length} color={driftList.length > 0 ? "text-red-600" : "text-green-600"} />
              <KpiCard icon={FileText} label="Plans" value={planList.length} color="text-teal-600" />
              <KpiCard icon={Database} label="Outputs" value={outputs?.outputs ? Object.keys(outputs.outputs).length : 0} color="text-cyan-600" />
              <KpiCard icon={Activity} label="Categories" value={categories.length} color="text-orange-600" />
              <KpiCard icon={Globe} label="Current WS" value={currentWs?.workspace || "default"} color="text-green-600" />
            </div>

            {/* Resource categories breakdown */}
            {categories.length > 0 && (
              <div className="rounded-xl border border-gray-200 dark:border-gray-700 p-4">
                <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">Resource Categories</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {categories.map(cat => {
                    const Icon = resourceTypeIcons[cat] || Box
                    const count = categoryCounts[cat] || 0
                    return (
                      <div key={cat} className="flex items-center gap-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg p-3">
                        <Icon size={20} className="text-gray-500 dark:text-gray-400" />
                        <div>
                          <p className="text-xs text-gray-500 dark:text-gray-400 capitalize">{cat}</p>
                          <p className="text-lg font-bold text-gray-900 dark:text-white">{count}</p>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {/* Provider summary */}
            {providerList.length > 0 && (
              <div className="rounded-xl border border-gray-200 dark:border-gray-700 p-4">
                <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">Providers</h3>
                <div className="flex flex-wrap gap-2">
                  {providerList.map((p: any) => (
                    <span key={p.name || p} className="px-3 py-1 rounded-lg bg-gray-100 dark:bg-gray-700 text-xs font-medium text-gray-700 dark:text-gray-300">
                      {p.name || p} {p.version ? `v${p.version}` : ""}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        )}

        {activeTab === "Workspaces" && (
          <motion.div variants={stagger()} initial="hidden" animate="visible" className="space-y-4">
            {wsLoading ? (
              <div className="flex items-center justify-center py-12"><Loader2 size={32} className="animate-spin text-gray-400" /></div>
            ) : (workspaces?.workspaces || []).length === 0 ? (
              <div className="text-center py-12 text-gray-500 dark:text-gray-400">No workspaces found</div>
            ) : (
              <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-700">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 dark:bg-gray-800">
                    <tr>
                      <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Workspace</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Current</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                    {(workspaces?.workspaces || []).map((w: string) => (
                      <tr key={w} className={`hover:bg-gray-50 dark:hover:bg-gray-800/50 ${w === (currentWs?.workspace || "default") ? 'bg-blue-50 dark:bg-blue-900/10' : ''}`}>
                        <td className="px-4 py-3 font-medium text-gray-900 dark:text-white">{w}</td>
                        <td className="px-4 py-3">{w === (currentWs?.workspace || "default") ? <StatusBadge status="active" /> : "-"}</td>
                        <td className="px-4 py-3">
                          <div className="flex gap-2">
                            <button onClick={() => initMut.mutate({ workspace: w })} className="text-xs px-2 py-1 rounded bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-blue-900/50">Init</button>
                            <button onClick={() => planMut.mutate({ workspace: w })} className="text-xs px-2 py-1 rounded bg-purple-50 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400 hover:bg-purple-100 dark:hover:bg-purple-900/50">Plan</button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </motion.div>
        )}

        {activeTab === "State" && (
          <motion.div variants={stagger()} initial="hidden" animate="visible" className="space-y-4">
            <div className="flex items-center justify-between">
              <p className="text-sm text-gray-500 dark:text-gray-400">{resourceCount} resources managed</p>
              <div className="flex gap-2">
                <button onClick={() => initMut.mutate({ workspace })} className="text-xs px-3 py-1.5 rounded-lg bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-blue-900/50">Init</button>
                <button onClick={() => validateMut.mutate()} className="text-xs px-3 py-1.5 rounded-lg bg-green-50 dark:bg-green-900/30 text-green-600 dark:text-green-400 hover:bg-green-100 dark:hover:bg-green-900/50">Validate</button>
              </div>
            </div>
            {resources.length === 0 ? (
              <div className="text-center py-12 text-gray-500 dark:text-gray-400">No resources in state</div>
            ) : (
              <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-700">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 dark:bg-gray-800">
                    <tr>
                      <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Address</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Type</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Category</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Provider</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                    {resources.map((r: any, i: number) => (
                      <tr key={i} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                        <td className="px-4 py-3 font-mono text-xs text-gray-900 dark:text-white">{r.address || r.name || "-"}</td>
                        <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{r.type || "-"}</td>
                        <td className="px-4 py-3"><ResourceCategoryBadge category={r.category || "other"} /></td>
                        <td className="px-4 py-3 text-gray-500 dark:text-gray-400">{r.provider || (r.type || "").split("_")[0] || "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </motion.div>
        )}

        {activeTab === "Outputs" && (
          <motion.div variants={stagger()} initial="hidden" animate="visible" className="space-y-4">
            {!outputs?.outputs || Object.keys(outputs.outputs).length === 0 ? (
              <div className="text-center py-12 text-gray-500 dark:text-gray-400">No outputs defined</div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {Object.entries(outputs.outputs).map(([key, val]: [string, any]) => (
                  <div key={key} className="rounded-xl border border-gray-200 dark:border-gray-700 p-4">
                    <p className="text-sm font-semibold text-gray-900 dark:text-white mb-1">{key}</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">{val.type || "unknown"}</p>
                    <pre className="text-xs bg-gray-50 dark:bg-gray-800/50 rounded-lg p-2 overflow-x-auto text-gray-700 dark:text-gray-300">
                      {typeof val.value === 'object' ? JSON.stringify(val.value, null, 2) : String(val.value)}
                    </pre>
                  </div>
                ))}
              </div>
            )}
          </motion.div>
        )}

        {activeTab === "Providers" && (
          <motion.div variants={stagger()} initial="hidden" animate="visible" className="space-y-4">
            {providerList.length === 0 ? (
              <div className="text-center py-12 text-gray-500 dark:text-gray-400">No providers found</div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {providerList.map((p: any, i: number) => (
                  <div key={i} className="rounded-xl border border-gray-200 dark:border-gray-700 p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <Box size={18} className="text-teal-600" />
                      <p className="text-sm font-semibold text-gray-900 dark:text-white">{p.name || p}</p>
                    </div>
                    {p.version && <p className="text-xs text-gray-500 dark:text-gray-400">v{p.version}</p>}
                    {p.source && <p className="text-xs text-gray-500 dark:text-gray-400">{p.source}</p>}
                  </div>
                ))}
              </div>
            )}
          </motion.div>
        )}

        {activeTab === "Graph" && (
          <motion.div variants={stagger()} initial="hidden" animate="visible" className="space-y-4">
            {!graph?.graph ? (
              <div className="text-center py-12 text-gray-500 dark:text-gray-400">No graph data available</div>
            ) : (
              <div className="space-y-4">
                <p className="text-sm text-gray-500 dark:text-gray-400">{graph.graph.nodes?.length || 0} nodes, {graph.graph.edges?.length || 0} edges</p>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  <div className="rounded-xl border border-gray-200 dark:border-gray-700 p-4 max-h-[500px] overflow-auto">
                    <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">Nodes</h3>
                    {(graph.graph.nodes || []).map((n: any, i: number) => (
                      <div key={i} className="flex items-center gap-2 text-xs py-1.5 border-b border-gray-100 dark:border-gray-700 last:border-0">
                        <span className="w-2 h-2 rounded-full bg-blue-500" />
                        <span className="text-gray-900 dark:text-white font-mono">{n.id || n.name || n.address || `node-${i}`}</span>
                        {n.type && <span className="text-gray-500 dark:text-gray-400">({n.type})</span>}
                        {n.category && <ResourceCategoryBadge category={n.category} />}
                      </div>
                    ))}
                  </div>
                  <div className="rounded-xl border border-gray-200 dark:border-gray-700 p-4 max-h-[500px] overflow-auto">
                    <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">Edges</h3>
                    {(graph.graph.edges || []).map((e: any, i: number) => (
                      <div key={i} className="flex items-center gap-2 text-xs py-1.5 border-b border-gray-100 dark:border-gray-700 last:border-0">
                        <span className="text-gray-600 dark:text-gray-400 font-mono">{e.source || e.from}</span>
                        <ArrowRight size={12} className="text-gray-400" />
                        <span className="text-gray-600 dark:text-gray-400 font-mono">{e.target || e.to}</span>
                        {e.label && <span className="text-gray-500 dark:text-gray-400">({e.label})</span>}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </motion.div>
        )}

        {activeTab === "Drift" && (
          <motion.div variants={stagger()} initial="hidden" animate="visible" className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <KpiCard icon={AlertTriangle} label="Drifts" value={driftList.length} color={driftList.length > 0 ? "text-red-600" : "text-green-600"} />
              <KpiCard icon={Activity} label="Risk Score" value={drift?.risk_score || 0} color={(drift?.risk_score || 0) > 50 ? "text-red-600" : (drift?.risk_score || 0) > 20 ? "text-yellow-600" : "text-green-600"} />
              <KpiCard icon={Shield} label="Scanned" value={resourceCount} color="text-blue-600" />
            </div>
            {driftList.length === 0 ? (
              <div className="text-center py-12 text-green-600 dark:text-green-400 flex items-center justify-center gap-2">
                <CheckCircle size={20} /> No drift detected
              </div>
            ) : (
              <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-700">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 dark:bg-gray-800">
                    <tr>
                      <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Resource</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Type</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Change</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Risk</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Detail</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                    {driftList.map((d: any, i: number) => (
                      <tr key={i} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                        <td className="px-4 py-3 font-mono text-xs text-gray-900 dark:text-white">{d.address || d.resource || d.name || "-"}</td>
                        <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{d.type || "-"}</td>
                        <td className="px-4 py-3"><StatusBadge status={d.change || d.action || d.status || "modified"} /></td>
                        <td className="px-4 py-3">
                          <span className={`px-2 py-0.5 rounded text-xs font-medium ${(d.risk_score || d.risk || 0) > 50 ? 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300' : (d.risk_score || d.risk || 0) > 20 ? 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300' : 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300'}`}>
                            {d.risk_score || d.risk || 0}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-xs text-gray-500 dark:text-gray-400 max-w-xs truncate">{d.message || d.detail || ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </motion.div>
        )}

        {activeTab === "Plans" && (
          <motion.div variants={stagger()} initial="hidden" animate="visible" className="space-y-4">
            <div className="flex items-center gap-4 mb-4">
              <label className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
                <input type="checkbox" id="destroy" className="rounded" />
                <span>Destroy plan</span>
              </label>
              <button onClick={() => planMut.mutate({ workspace })} disabled={planMut.isPending}
                className="px-4 py-2 text-sm font-medium bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 flex items-center gap-2">
                {planMut.isPending ? <Loader2 size={14} className="animate-spin" /> : <PlayCircle size={14} />}
                New Plan
              </button>
            </div>

            {planMut.data && (
              <div className="rounded-xl border border-gray-200 dark:border-gray-700 p-4 bg-blue-50 dark:bg-blue-900/10">
                <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-2">Plan Result</h3>
                <pre className="text-xs text-gray-700 dark:text-gray-300 max-h-[400px] overflow-auto">{JSON.stringify(planMut.data, null, 2)}</pre>
                {planMut.data.plan?.plan_id && (
                  <button onClick={() => applyMut.mutate({ planId: planMut.data.plan.plan_id, workspace })}
                    className="mt-3 px-4 py-2 text-sm font-medium bg-green-600 text-white rounded-lg hover:bg-green-700">
                    Apply Plan
                  </button>
                )}
              </div>
            )}

            {applyMut.data && (
              <div className="rounded-xl border border-green-200 dark:border-green-800 p-4 bg-green-50 dark:bg-green-900/10">
                <h3 className="text-sm font-semibold text-green-700 dark:text-green-300 mb-2">Apply Result</h3>
                <pre className="text-xs text-gray-700 dark:text-gray-300 max-h-[400px] overflow-auto">{JSON.stringify(applyMut.data, null, 2)}</pre>
              </div>
            )}

            {planList.length > 0 && (
              <div className="rounded-xl border border-gray-200 dark:border-gray-700 p-4">
                <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">Plan History</h3>
                <div className="space-y-2 max-h-[400px] overflow-auto">
                  {planList.map((p: any, i: number) => (
                    <div key={i} className="flex items-center justify-between text-xs bg-gray-50 dark:bg-gray-800/50 rounded-lg p-3">
                      <div className="flex items-center gap-3">
                        <FileText size={14} className="text-gray-400" />
                        <span className="font-mono text-gray-900 dark:text-white">{p.plan_id || `plan-${i}`}</span>
                        <span className="text-gray-500">{p.workspace || "-"}</span>
                      </div>
                      <div className="flex items-center gap-3">
                        {p.changes && <span className="text-gray-500">{p.changes.add || 0}+ / {p.changes.change || 0}~ / {p.changes.destroy || 0}-</span>}
                        <span className="text-gray-400">{p.created_at ? new Date(p.created_at).toLocaleString() : ""}</span>
                        {p.status && <StatusBadge status={p.status} />}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        )}

        {activeTab === "Correlation" && (
          <motion.div variants={stagger()} initial="hidden" animate="visible" className="space-y-4">
            <div className="flex items-center gap-4 mb-4">
              <input
                type="text"
                placeholder="Workspace name (default: current)"
                value={workspace}
                onChange={e => setWorkspace(e.target.value)}
                className="flex-1 border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button onClick={() => correlateMut.mutate(workspace)} disabled={correlateMut.isPending}
                className="px-4 py-2 text-sm font-medium bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
                {correlateMut.isPending ? <Loader2 size={14} className="animate-spin" /> : "Correlate"}
              </button>
              <button onClick={() => destroyMut.mutate(workspace)} disabled={destroyMut.isPending}
                className="px-4 py-2 text-sm font-medium bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50">
                {destroyMut.isPending ? <Loader2 size={14} className="animate-spin" /> : "Destroy"}
              </button>
            </div>
            {correlateMut.data && (
              <pre className="text-xs text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-gray-800/50 rounded-xl p-4 max-h-[600px] overflow-auto">
                {JSON.stringify(correlateMut.data, null, 2)}
              </pre>
            )}
          </motion.div>
        )}
      </motion.div>
    </CortexShell>
  )
}
